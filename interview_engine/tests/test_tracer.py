from interview_engine.app.visualization.services.tracer import PythonTracer
from interview_engine.app.visualization.services.event_parser import EventParser
from interview_engine.app.visualization.services.timeline_builder import TimelineBuilder

def test_python_tracer_captures_replayable_events_and_stdout():
    events = PythonTracer().trace("total = 0\nfor value in [1, 2, 3]:\n    total += value\nprint(total)")
    parsed = EventParser().parse(events)
    steps = TimelineBuilder().build("trace-1", parsed)
    assert steps
    assert any(step.event_type == "LINE_EXECUTED" for step in steps)
    assert steps[-1].stdout.strip() == "6"
    assert steps[-1].variable_history["total"][-1] == 6

def test_python_tracer_records_exception_without_raising():
    events = PythonTracer().trace("value = 1 / 0")
    assert any(event.event_type == "EXCEPTION" for event in events)

def test_python_tracer_rejects_imports():
    try:
        PythonTracer().trace("import os")
    except ValueError as exc:
        assert "Imports" in str(exc)
    else:
        raise AssertionError("Expected imports to be rejected")

def test_python_tracer_rejects_dunder_escape():
    events = PythonTracer().trace("().__class__.__base__.__subclasses__()")
    assert events[-1].event_type == "EXCEPTION"
    assert "Dangerous dunder" in (events[-1].error or "")

def test_python_tracer_terminates_infinite_loop():
    events = PythonTracer().trace("while True:\n    pass")
    assert events[-1].event_type == "EXCEPTION"
    assert "timed out" in (events[-1].error or "").lower() or "limit" in (events[-1].error or "").lower()

def test_python_tracer_drains_large_pipe_results_without_false_timeout():
    code = "\n".join(
        [f"payload_{index} = ['x' * 200] * 50" for index in range(8)]
        + ["print(len(payload_0))"]
    )

    events = PythonTracer().trace(code)

    assert events
    assert not any(
        event.event_type == "EXCEPTION"
        and "timed out" in (event.error or "").lower()
        for event in events
    )
    assert any(event.event_type == "LINE_EXECUTED" for event in events)

def test_python_tracer_captures_cyclic_user_object_structure():
    code = """class Node:
    def __init__(self, value):
        self.value = value
        self.next = None

root = Node(1)
root.next = Node(2)
root.next.next = root
print(root.value)
"""

    events = PythonTracer().trace(code)
    roots = [event.locals.get("root") for event in events if isinstance(event.locals.get("root"), dict)]

    structured_root = next(
        value for value in roots
        if value.get("__type__") == "Node"
        and isinstance(value.get("attrs", {}).get("next"), dict)
        and isinstance(value["attrs"]["next"].get("attrs", {}).get("next"), dict)
        and value["attrs"]["next"]["attrs"]["next"].get("__cycle__") is True
    )
    next_node = structured_root["attrs"]["next"]
    assert next_node["__type__"] == "Node"
    assert next_node["attrs"]["next"]["__cycle__"] is True
