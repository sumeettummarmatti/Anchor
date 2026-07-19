import logging
from ..models.execution_trace import AIAnnotation, ExecutionStep
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry

logger = logging.getLogger(__name__)

class AIExplainer:
    """Provider boundary for per-step explanations; deterministic fallback is default."""
    def __init__(self, llm: LLMClient = None): self.llm = llm
    def explain(self, trace_id: str, step: ExecutionStep) -> AIAnnotation:
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, "Explain one program execution step concisely. Return JSON with explanation, detected_concept, and difficulty.", str({"code": step.executed_code, "event_type": step.event_type, "locals": step.locals, "call_stack": step.call_stack}), "step_explainer")
                return AIAnnotation(trace_id, step.step_number, str(result["explanation"]), str(result.get("detected_concept", "execution flow")), str(result.get("difficulty", "intermediate")), "groq")
            except LLMAuthError:
                raise
            except (KeyError, LLMCallError) as exc:
                logger.warning("Step explainer falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        if step.event_type == "EXCEPTION":
            explanation = "Execution raised an exception at this point. Inspect the current variables and call stack."
            concept = "exception handling"
        elif step.event_type == "FUNCTION_CALL":
            explanation = "A function call created or entered a new stack frame."
            concept = "function call"
        elif step.event_type == "FUNCTION_RETURN":
            explanation = "The current function returned and its stack frame is about to be removed."
            concept = "function return"
        elif step.executed_code.startswith("for ") or step.executed_code.startswith("while "):
            explanation = "This line controls loop execution and determines whether another iteration runs."
            concept = "loop"
        elif "=" in step.executed_code:
            explanation = "This statement updates program state by assigning a value to a variable."
            concept = "variable assignment"
        else:
            explanation = "This statement executes with the variables and call stack shown for the current step."
            concept = "execution flow"
        return AIAnnotation(trace_id, step.step_number, explanation, concept, "introductory", "local_fallback")
