from typing import Any, List, Optional
import re
from ..schemas.submission_context import SubmissionContext
import logging
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)


def code_reference(context: dict) -> str:
    code = str(context.get("code", "")).strip()
    function = re.search(r"\bdef\s+([A-Za-z_]\w*)", code)
    if function:
        return f"`{function.group(1)}`"
    identifier = re.search(r"\b([A-Za-z_]\w*)\b", code)
    if identifier:
        return f"`{identifier.group(1)}`"
    first_line = next((line.strip() for line in code.splitlines() if line.strip()), "the submitted code")
    return f"`{first_line[:80]}`"


def fallback_code_questions(context: dict) -> List[str]:
    reference = code_reference(context)
    return [
        f"Looking at {reference}, walk me through your overall approach and why it solves the problem.",
        f"What data structure does {reference} rely on, why is it appropriate here, and what invariant does it preserve?",
        f"What are the time and space complexities of {reference}? Point to the operations in this code that create those costs.",
        f"Which edge cases could change the behavior of {reference}, and where does the submitted code handle them?",
        f"What alternative approach could replace the strategy in {reference}, and what trade-off would that introduce?",
    ]


def question_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for field in ("question", "text", "prompt"):
            candidate = value.get(field)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""
    return str(value).strip()


def normalized_questions(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [text for text in (question_text(value) for value in values[:5]) if text]


class Planner:
    def __init__(self, llm: Optional[LLMClient] = None): self.llm = llm
    def create_plan(self, context: Any, company: Optional[str] = None, style: str = "Friendly") -> List[str]:
        data = context if isinstance(context, dict) else context.model_dump()
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, "Create a technical interview plan from the submitted source code. Return JSON with a questions array of exactly five concise questions. Keep every question grounded in source_code, but cover these general interview dimensions in order: overall approach, chosen data structures and invariants, time and space complexity, edge cases, and an alternative approach with trade-offs. Refer to concrete code details where useful; do not produce unrelated generic questions.", str({"problem": data["problem_title"], "description": data["problem_description"], "difficulty": data["difficulty"], "source_code": data["code"], "company": company, "style": style, "execution_status": data.get("execution_status"), "struggle_indicators": data.get("struggle_indicators", [])}), "planner")
                questions = normalized_questions(result.get("questions", []))
                if len(questions) >= 3: return questions
                logger.error("LLM response/schema failure component=planner detail=questions must contain at least three items")
                repaired = repair_json_with_retry(self.llm, result, "questions: an array containing at least three concise strings", "planner")
                questions = normalized_questions(repaired.get("questions", []))
                if len(questions) >= 3:
                    return questions
                logger.error("Planner repair returned invalid questions; using fallback")
            except LLMAuthError as exc:
                logger.warning("Planner falling back after LLM authentication failure detail=%s", str(exc)[:240])
            except LLMCallError as exc:
                logger.warning("Planner falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        return fallback_code_questions(data)
