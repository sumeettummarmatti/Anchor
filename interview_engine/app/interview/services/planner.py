from typing import Any, List, Optional
from ..schemas.submission_context import SubmissionContext
import logging
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)

class Planner:
    def __init__(self, llm: Optional[LLMClient] = None): self.llm = llm
    def create_plan(self, context: Any, company: Optional[str] = None, style: str = "Friendly") -> List[str]:
        data = context if isinstance(context, dict) else context.model_dump()
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, "Create a technical interview plan. Return JSON with a questions array of exactly five concise questions.", str({"problem": data["problem_title"], "description": data["problem_description"], "difficulty": data["difficulty"], "company": company, "style": style, "execution_status": data.get("execution_status"), "struggle_indicators": data.get("struggle_indicators", [])}), "planner")
                questions = result.get("questions", [])
                if isinstance(questions, list) and len(questions) >= 3: return [str(question) for question in questions[:5]]
                logger.error("LLM response/schema failure component=planner detail=questions must contain at least three items")
                repaired = repair_json_with_retry(self.llm, result, "questions: an array containing at least three concise strings", "planner")
                questions = repaired.get("questions", [])
                if isinstance(questions, list) and len(questions) >= 3:
                    return [str(question) for question in questions[:5]]
                logger.error("Planner repair returned invalid questions; using fallback")
            except LLMAuthError:
                raise
            except LLMCallError as exc:
                logger.warning("Planner falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        return [
            "Explain your approach and why it solves the problem.",
            "What are the time and space complexities of your solution?",
            "Which edge cases did you consider, and how does your code handle them?",
            "Describe an alternative approach and its trade-offs.",
            "What would you optimize if this solution had to handle much larger inputs?",
        ]
