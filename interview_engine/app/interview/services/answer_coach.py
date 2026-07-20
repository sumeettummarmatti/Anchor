import logging
from typing import Optional

from ...core.llm import LLMCallError, LLMClient, complete_json_with_retry, repair_json_with_retry
from .planner import code_reference

logger = logging.getLogger(__name__)


class AnswerCoach:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm

    def generate(self, question: str, context: dict) -> tuple[str, str]:
        if self.llm:
            try:
                result = complete_json_with_retry(
                    self.llm,
                    "Generate a strong, concise technical-interview reference answer. Base it only on the question and submitted source code. Explain the approach, relevant data structure, complexity, and an applicable edge case when relevant. Return JSON with a non-empty answer string.",
                    str({"question": question, "source_code": context.get("code", ""), "problem": context.get("problem_description", "")}),
                    "answer_coach",
                )
                answer = result.get("answer")
                if isinstance(answer, str) and answer.strip():
                    return answer.strip(), "llm"
                repaired = repair_json_with_retry(self.llm, result, "answer: a non-empty technical interview answer string", "answer_coach")
                answer = repaired.get("answer")
                if isinstance(answer, str) and answer.strip():
                    return answer.strip(), "llm"
            except LLMCallError as exc:
                logger.warning("Answer coach falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])

        reference = code_reference(context)
        return (
            f"Looking at {reference}, I would first explain the flow of the implementation and the invariant it maintains. "
            "I would then name the data structure used by this code and why its operations fit the problem. "
            "Finally, I would state the time and space complexity from the loops and stored state, then mention an edge case this implementation should handle.",
            "fallback",
        )
