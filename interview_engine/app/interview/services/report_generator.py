from ..schemas.report import InterviewReport
import logging
from pydantic import ValidationError
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)

SCORE_FIELDS = (
    "technical_accuracy",
    "communication",
    "complexity_understanding",
    "edge_case_reasoning",
    "confidence",
)


def evaluation_score(evaluation: dict) -> float:
    return sum(float(evaluation.get(field, 0)) for field in SCORE_FIELDS) / len(SCORE_FIELDS)


def all_scores_zero(evaluation: dict) -> bool:
    return all(float(evaluation.get(field, 0)) == 0 for field in SCORE_FIELDS)


class ReportGenerator:
    def __init__(self, llm: LLMClient = None): self.llm = llm
    def generate(self, interview_id: str, evaluations: list[dict], context: dict) -> InterviewReport:
        if not evaluations:
            return InterviewReport(
                interview_id=interview_id,
                overall_score=0.0,
                strengths=[],
                weaknesses=["No answer was submitted."],
                communication_feedback="No answer was submitted, so communication could not be evaluated.",
                recommended_topics=[context.get("difficulty", "DSA")],
                improvement_plan=["Submit at least one answer before finishing the interview."],
                summary="Interview was not scored because no answers were submitted.",
            )
        authoritative_score = round(
            sum(evaluation_score(evaluation) for evaluation in evaluations) / len(evaluations),
            1,
        )
        if all(all_scores_zero(evaluation) for evaluation in evaluations):
            return InterviewReport(
                interview_id=interview_id,
                overall_score=0.0,
                strengths=[],
                weaknesses=["No technical approach was provided."],
                communication_feedback="The submitted response indicated uncertainty and did not provide an explanation to evaluate.",
                recommended_topics=[context.get("difficulty", "DSA")],
                improvement_plan=["Explain one small next step or ask for a hint before continuing."],
                summary="The submitted responses did not demonstrate knowledge of the problem, so the interview score is 0/10.",
            )
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, f"Create an interview report. Return JSON matching the report schema: interview_id, overall_score, strengths, weaknesses, communication_feedback, recommended_topics, improvement_plan, summary. The authoritative overall_score is {authoritative_score}/10, computed from the answer evaluations. Return that exact score and do not infer a different score from the submitted code.", str({"interview_id": interview_id, "evaluations": evaluations, "submission": context}), "report")
                result["interview_id"] = interview_id
                result["overall_score"] = authoritative_score
                result["provider_used"] = "llm"
                return InterviewReport(**result)
            except ValidationError as exc:
                logger.error("LLM schema validation failure component=report type=%s detail=%s", type(exc).__name__, str(exc)[:240])
                try:
                    repaired = repair_json_with_retry(self.llm, result, f"overall_score must be exactly {authoritative_score}; strengths, weaknesses, recommended_topics, improvement_plan: string arrays; communication_feedback, summary: strings", "report")
                    repaired["interview_id"] = interview_id
                    repaired["overall_score"] = authoritative_score
                    repaired["provider_used"] = "llm"
                    return InterviewReport(**repaired)
                except (LLMCallError, ValidationError) as repair_exc:
                    logger.warning("Report repair failed; using fallback type=%s detail=%s", type(repair_exc).__name__, str(repair_exc)[:240])
            except LLMAuthError as exc:
                logger.warning("Report generator falling back after LLM authentication failure detail=%s", str(exc)[:240])
            except LLMCallError as exc:
                logger.warning("Report generator falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        score = authoritative_score
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
