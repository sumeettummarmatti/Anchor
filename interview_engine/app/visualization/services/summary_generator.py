from collections import Counter
import logging
from pydantic import ValidationError
from ..schemas.visualization import TraceSummary
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)

class SummaryGenerator:
    def __init__(self, llm: LLMClient = None): self.llm = llm
    def generate(self, trace_id, source_code, steps) -> TraceSummary:
        events = Counter(step.event_type for step in steps)
        calls = events.get("FUNCTION_CALL", 0)
        returns = events.get("FUNCTION_RETURN", 0)
        loop_lines = sum(1 for step in steps if step.executed_code.startswith(("for ", "while ")))
        variables = steps[-1].variable_history if steps else {}
        output = steps[-1].stdout if steps else ""
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, "Summarize this execution timeline. Return JSON matching the execution summary schema.", str({"source_code": source_code, "steps": [{"line": s.line_number, "code": s.executed_code, "event": s.event_type, "locals": s.locals} for s in steps[-80:]], "stdout": output}), "execution_summary")
                result["trace_id"] = trace_id
                result["execution_length"] = len(steps)
                result["provider_used"] = "llm"
                return TraceSummary(**result)
            except ValidationError as exc:
                logger.error("LLM schema validation failure component=execution_summary type=%s detail=%s", type(exc).__name__, str(exc)[:240])
                try:
                    repaired = repair_json_with_retry(self.llm, result, "algorithm_flow, recursion_summary, loop_behavior, final_output: strings; important_events: string array; variable_evolution: object; execution_length: integer", "execution_summary")
                    repaired["trace_id"] = trace_id
                    repaired["execution_length"] = len(steps)
                    repaired["provider_used"] = "llm"
                    return TraceSummary(**repaired)
                except (LLMCallError, ValidationError) as repair_exc:
                    logger.warning("Execution summary repair failed; using fallback type=%s detail=%s", type(repair_exc).__name__, str(repair_exc)[:240])
            except LLMAuthError:
                raise
            except LLMCallError as exc:
                logger.warning("Summary generator falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        important = [f"{count} {event.lower().replace('_', ' ')} event(s)" for event, count in events.items() if event in ("EXCEPTION", "FUNCTION_CALL", "FUNCTION_RETURN")]
        return TraceSummary(trace_id=trace_id,
            algorithm_flow="The source was executed in source-line order and recorded as replayable events.",
            important_events=important,
            recursion_summary=f"{calls} function call(s) and {returns} return event(s) were observed.",
            loop_behavior=f"{loop_lines} loop-control line event(s) were observed.",
            variable_evolution=variables,
            final_output=output,
            execution_length=len(steps),
            provider_used="fallback")
