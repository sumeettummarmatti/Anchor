from ..schemas.report import InterviewReport
import logging
from pydantic import ValidationError
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, llm: LLMClient = None): self.llm = llm
    def generate(self, interview_id: str, evaluations: list[dict], context: dict) -> InterviewReport:
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, "Create an interview report. Return JSON matching the report schema: interview_id, overall_score, strengths, weaknesses, communication_feedback, recommended_topics, improvement_plan, summary.", str({"interview_id": interview_id, "evaluations": evaluations, "submission": context}), "report")
                result["interview_id"] = interview_id
                result["provider_used"] = "llm"
                return InterviewReport(**result)
            except ValidationError as exc:
                logger.error("LLM schema validation failure component=report type=%s detail=%s", type(exc).__name__, str(exc)[:240])
                try:
                    repaired = repair_json_with_retry(self.llm, result, "overall_score: number 0-10; strengths, weaknesses, recommended_topics, improvement_plan: string arrays; communication_feedback, summary: strings", "report")
                    repaired["interview_id"] = interview_id
                    repaired["provider_used"] = "llm"
                    return InterviewReport(**repaired)
                except (LLMCallError, ValidationError) as repair_exc:
                    logger.warning("Report repair failed; using fallback type=%s detail=%s", type(repair_exc).__name__, str(repair_exc)[:240])
            except LLMAuthError:
                raise
            except LLMCallError as exc:
                logger.warning("Report generator falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        if not evaluations:
            score = 0.0
        else:
            values = [sum(e[k] for k in ("technical_accuracy", "communication", "complexity_understanding", "edge_case_reasoning", "confidence")) / 5 for e in evaluations]
            score = round(sum(values) / len(values), 1)
        strengths = []
        weaknesses = []
        if evaluations and sum(e["technical_accuracy"] for e in evaluations) / len(evaluations) >= 7: strengths.append("Technical reasoning")
        if evaluations and sum(e["complexity_understanding"] for e in evaluations) / len(evaluations) < 7: weaknesses.append("Complexity analysis")
        if evaluations and sum(e["edge_case_reasoning"] for e in evaluations) / len(evaluations) < 7: weaknesses.append("Edge-case coverage")
        return InterviewReport(interview_id=interview_id, overall_score=score,
            strengths=strengths or ["Persistence through the interview"], weaknesses=weaknesses or ["Continue practicing concise explanations"],
            communication_feedback="Explain assumptions before conclusions and use examples.",
            recommended_topics=["Complexity analysis", "Edge cases", context.get("difficulty", "DSA")],
            improvement_plan=["Practice narrating the approach before coding.", "State time and space complexity explicitly."],
            summary=f"Interview completed for {context.get('problem_title', 'the submitted problem')} with an overall score of {score}/10.")
