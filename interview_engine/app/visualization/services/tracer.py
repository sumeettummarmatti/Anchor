import ast
import builtins
import io
import linecache
import sys
import importlib
import multiprocessing
import resource
import signal
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class RawExecutionEvent:
    event_type: str
    line_number: Optional[int]
    code: str
    locals: Dict[str, Any] = field(default_factory=dict)
    globals: Dict[str, Any] = field(default_factory=dict)
    call_stack: List[str] = field(default_factory=list)
    stdout: str = ""
    error: Optional[str] = None

class BaseTracer:
    def trace(self, code: str) -> List[RawExecutionEvent]:
        raise NotImplementedError

class PythonTracer(BaseTracer):
    """Deterministic line tracer for educational Python snippets.

    Execution is intentionally constrained to a small builtin set and a finite
    trace-event budget. Production deployments should execute untrusted code in
    a separate OS/container sandbox.
    """
    MAX_EVENTS = 10000
    WALL_TIMEOUT_SECONDS = 3
    CPU_LIMIT_SECONDS = 2
    MEMORY_LIMIT_BYTES = 256 * 1024 * 1024
    DANGEROUS_DUNDERS = {
        "__class__", "__base__", "__bases__", "__subclasses__", "__globals__",
        "__code__", "__mro__", "__getattribute__", "__dict__", "__builtins__",
    }
    ALLOWED_MODULES = {"math", "statistics", "collections", "itertools", "functools", "heapq", "bisect"}
    ALLOWED_BUILTINS = {
        name: getattr(builtins, name) for name in
        ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
         "int", "isinstance", "issubclass", "len", "list", "map", "max", "min",
         "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple",
         "type", "zip", "print", "object", "super", "classmethod", "staticmethod",
         "property", "hasattr", "getattr", "setattr", "Exception", "BaseException",
         "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError", "AssertionError")
    }

    def trace(self, code: str) -> List[RawExecutionEvent]:
        """Trace code in a bounded worker process, never in the API process."""
        # Validate imports before spawning the worker so rejected modules remain
        # programmer-facing validation errors instead of being converted into
        # an execution-event payload by the worker's broad exception boundary.
        self._validate_imports(ast.parse(code, filename="<execution>"))
        parent_conn, child_conn = multiprocessing.Pipe(duplex=False)
        worker = multiprocessing.get_context("fork").Process(
            target=_trace_worker,
            args=(code, child_conn, self.MAX_EVENTS, self.CPU_LIMIT_SECONDS, self.MEMORY_LIMIT_BYTES),
            daemon=True,
        )
        worker.start()
        child_conn.close()
        result = None
        received = False
        deadline = time.monotonic() + self.WALL_TIMEOUT_SECONDS
        try:
            # Read while the worker is alive. A large result can fill the pipe
            # buffer; waiting in join() first would deadlock the worker before
            # it can finish sending the trace.
            while time.monotonic() < deadline:
                remaining = max(0.01, min(0.05, deadline - time.monotonic()))
                if parent_conn.poll(remaining):
                    try:
                        result = parent_conn.recv()
                        received = True
                    except (EOFError, OSError):
                        pass
                    break
                if not worker.is_alive():
                    break

            worker.join(0.5)
            timed_out = worker.is_alive()
            if timed_out:
                worker.terminate()
                worker.join(1)

            if received:
                if isinstance(result, list):
                    return result
                return [RawExecutionEvent("EXCEPTION", None, "", error=str(result))]
            if timed_out:
                return [RawExecutionEvent("EXCEPTION", None, "", error="Execution timed out and was terminated")]
            return [RawExecutionEvent("EXCEPTION", None, "", error="Execution worker exited without a trace")]
        finally:
            parent_conn.close()

    @classmethod
    def _validate_imports(cls, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            if any(name not in cls.ALLOWED_MODULES for name in names):
                raise ValueError("Imports are restricted to safe standard-library modules: " + ", ".join(sorted(cls.ALLOWED_MODULES)))

    def _trace_in_process(self, code: str, max_events: Optional[int] = None) -> List[RawExecutionEvent]:
        tree = ast.parse(code, filename="<execution>")
        self._validate_imports(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in self.DANGEROUS_DUNDERS:
                raise ValueError("Dangerous dunder attribute access is not allowed")
            if isinstance(node, ast.Name) and node.id in self.DANGEROUS_DUNDERS:
                raise ValueError("Dangerous dunder access is not allowed")
        filename = "<execution>"
        linecache.cache[filename] = (len(code), None, code.splitlines(True), filename)
        events: List[RawExecutionEvent] = []
        output = io.StringIO()
        safe_builtins = dict(self.ALLOWED_BUILTINS)
        safe_builtins["__import__"] = self._safe_import
        safe_builtins["__build_class__"] = builtins.__build_class__
        namespace: Dict[str, Any] = {"__builtins__": safe_builtins, "__name__": "__main__"}
        previous_trace = sys.gettrace()

        SNAPSHOT_MAX_ITEMS = 50
        SNAPSHOT_MAX_DEPTH = 8
        SNAPSHOT_MAX_OBJECTS = 200
        execution_module = namespace["__name__"]

        def snapshot(value: Any, visited: Optional[set] = None, depth: int = 0) -> Any:
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            visited = visited if visited is not None else set()
            is_user_object = (
                hasattr(value, "__dict__")
                and not isinstance(value, type)
                and getattr(type(value), "__module__", None) == execution_module
            )
            is_container = isinstance(value, (list, tuple, set, dict))
            if not is_user_object and not is_container:
                return repr(value)[:200]

            reference = id(value)
            if reference in visited:
                return {"__ref__": reference, "__cycle__": True}
            if len(visited) >= SNAPSHOT_MAX_OBJECTS or depth >= SNAPSHOT_MAX_DEPTH:
                result = {"__ref__": reference, "__truncated__": True}
                if is_user_object:
                    result["__type__"] = type(value).__name__
                return result
            visited.add(reference)

            if isinstance(value, (list, tuple, set)):
                return [snapshot(item, visited, depth + 1) for item in list(value)[:SNAPSHOT_MAX_ITEMS]]
            if isinstance(value, dict):
                return {str(k): snapshot(v, visited, depth + 1) for k, v in list(value.items())[:SNAPSHOT_MAX_ITEMS]}
            try:
                attributes = vars(value)
            except (TypeError, AttributeError):
                return repr(value)[:200]
            return {
                "__ref__": reference,
                "__type__": type(value).__name__,
                "attrs": {
                    str(key): snapshot(attribute, visited, depth + 1)
                    for key, attribute in list(attributes.items())[:SNAPSHOT_MAX_ITEMS]
                },
            }

        def frame_stack(frame) -> List[str]:
            stack = []
            current = frame
            while current:
                if current.f_code.co_filename == filename:
                    stack.append(current.f_code.co_name)
                current = current.f_back
            return list(reversed(stack))

        def record(event_type: str, frame, error: Optional[str] = None):
            if len(events) >= (max_events or self.MAX_EVENTS):
                raise RuntimeError("Execution exceeded the trace event limit")
            line_no = frame.f_lineno if frame.f_code.co_filename == filename else None
            source_line = linecache.getline(filename, line_no).strip() if line_no else ""
            visited = set()
            local_values = {key: snapshot(value, visited) for key, value in frame.f_locals.items() if not key.startswith("__")}
            global_values = {key: snapshot(value, visited) for key, value in frame.f_globals.items() if key not in ("__builtins__", "__name__") and not key.startswith("__")}
            events.append(RawExecutionEvent(event_type, line_no, source_line, local_values, global_values, frame_stack(frame), output.getvalue(), error))

        def trace_fn(frame, event, arg):
            if frame.f_code.co_filename != filename:
                return trace_fn
            if event == "call":
                record("FUNCTION_CALL", frame)
            elif event == "line":
                record("LINE_EXECUTED", frame)
            elif event == "return":
                record("FUNCTION_RETURN", frame)
            elif event == "exception":
                record("EXCEPTION", frame, repr(arg[1]))
            return trace_fn

        try:
            sys.settrace(trace_fn)
            with redirect_stdout(output):
                exec(compile(tree, filename, "exec"), namespace, namespace)
        except Exception as exc:
            if not events or events[-1].event_type != "EXCEPTION":
                events.append(RawExecutionEvent("EXCEPTION", None, "", {}, {}, [], output.getvalue(), repr(exc)))
        finally:
            sys.settrace(previous_trace)
            linecache.cache.pop(filename, None)
        return events

    def _safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root not in self.ALLOWED_MODULES or level:
            raise ImportError("Import is not allowed in the execution sandbox")
        return importlib.import_module(name)

def _trace_worker(code: str, connection, max_events: int, cpu_limit: int, memory_limit: int):
    """Worker entry point. It has no access to the API process state."""
    try:
        def bounded_limit(kind, requested):
            soft, hard = resource.getrlimit(kind)
            ceiling = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            try:
                resource.setrlimit(kind, (ceiling, hard))
            except (ValueError, OSError, PermissionError):
                # Some macOS builds reject RLIMIT_AS changes. The parent-side
                # wall timeout still guarantees termination in that case.
                return False
            return True

        bounded_limit(resource.RLIMIT_CPU, cpu_limit)
        bounded_limit(resource.RLIMIT_AS, memory_limit)
        # Existing descriptors (including the result pipe) remain usable, while
        # the restricted builtins/import allowlist prevents new file/network IO.
        bounded_limit(resource.RLIMIT_NOFILE, 32)
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("Execution timed out")))
        signal.alarm(cpu_limit + 1)
        result = PythonTracer()._trace_in_process(code, max_events)
        signal.alarm(0)
        connection.send(result)
    except BaseException as exc:
        try:
            connection.send([RawExecutionEvent("EXCEPTION", None, "", error=f"{type(exc).__name__}: {exc}")])
        except Exception:
            pass
    finally:
        connection.close()
