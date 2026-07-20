from ..schemas.evaluation import Evaluation
import logging
import re
from pydantic import ValidationError
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry

logger = logging.getLogger(__name__)

NO_KNOWLEDGE_RESPONSES = {
    "i dont know", "i do not know", "idk", "no idea", "not sure",
    "i am not sure", "i cannot answer", "i cant answer",
}


def is_explicit_no_knowledge_answer(answer: str) -> bool:
    normalized = re.sub(r"[^a-z0-9 ]+", "", answer.lower()).strip()
    return normalized in NO_KNOWLEDGE_RESPONSES


def all_scores_zero(evaluation: Evaluation) -> bool:
    return all(
        score == 0
        for score in (
            evaluation.technical_accuracy,
            evaluation.communication,
            evaluation.complexity_understanding,
            evaluation.edge_case_reasoning,
            evaluation.confidence,
        )
    )


def minimum_attempt_score(evaluation: Evaluation) -> Evaluation:
    """Never treat a non-empty attempted answer as an explicit no-answer response."""
    if not all_scores_zero(evaluation):
        return evaluation
    return Evaluation(
        technical_accuracy=1,
        communication=1,
        complexity_understanding=1,
        edge_case_reasoning=1,
        confidence=1,
        feedback="Your response is an attempt, but it needs a concrete approach, reasoning, and examples to earn a stronger score.",
        provider_used=evaluation.provider_used,
    )


class Evaluator:
    def __init__(self, llm: LLMClient = None): self.llm = llm
    def evaluate(self, question: str, answer: str, context: dict) -> Evaluation:
        if is_explicit_no_knowledge_answer(answer):
            return Evaluation(
                technical_accuracy=0,
                communication=0,
                complexity_understanding=0,
                edge_case_reasoning=0,
                confidence=0,
                feedback="You said you do not know the answer. Try explaining one small next step or asking for a hint.",
            )
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm, """Evaluate a technical interview answer against the question and submitted code. Return JSON only with technical_accuracy, communication, complexity_understanding, edge_case_reasoning, confidence (all integers 0-10), and feedback. Assess the answer's actual reasoning, not keyword count. Score 0 in every category only for an explicit no-answer or refusal such as 'I don't know'. A partial but genuine attempt must receive a nuanced score: give credit for what is correct, score omitted areas lower rather than zeroing the whole card, and give specific feedback about the next improvement.""", str({"question": question, "answer": answer, "submission": context}), "evaluator")
                result["provider_used"] = "llm"
                evaluation = Evaluation(**result)
                if all_scores_zero(evaluation):
                    repaired = repair_json_with_retry(self.llm, result, "Reassess this non-empty interview answer. technical_accuracy, communication, complexity_understanding, edge_case_reasoning, confidence must be nuanced integers 0-10; do not return all zero unless the answer explicitly says it does not know. feedback must explain the assessment.", "evaluator")
                    repaired["provider_used"] = "llm"
                    evaluation = Evaluation(**repaired)
                return minimum_attempt_score(evaluation)
            except ValidationError as exc:
                logger.error("LLM schema validation failure component=evaluator type=%s detail=%s", type(exc).__name__, str(exc)[:240])
                try:
                    repaired = repair_json_with_retry(self.llm, result, "technical_accuracy, communication, complexity_understanding, edge_case_reasoning, confidence: integers 0-10; feedback: string", "evaluator")
                    repaired["provider_used"] = "llm"
                    return minimum_attempt_score(Evaluation(**repaired))
                except (LLMCallError, ValidationError) as repair_exc:
                    logger.warning("Evaluator repair failed; using fallback type=%s detail=%s", type(repair_exc).__name__, str(repair_exc)[:240])
            except LLMAuthError as exc:
                logger.warning("Evaluator falling back after LLM authentication failure detail=%s", str(exc)[:240])
            except LLMCallError as exc:
                logger.warning("Evaluator falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        # Coarse fallback only: this is deliberately not a fair grader. It keeps
        # the API functional without an LLM and must not be treated as a verdict.
        text = answer.lower().strip()
        words = re.findall(r"[a-z][a-z0-9_]*", text)
        unique_ratio = len(set(words)) / max(len(words), 1)
        sentences = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
        reasoning_verbs = ("because", "therefore", "approach", "choose", "handle", "returns", "iterate", "compare", "store")
        coherent = len(words) >= 8 and bool(sentences) and unique_ratio >= 0.42 and any(verb in text for verb in reasoning_verbs)
        code_identifiers = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(context.get("code", ""))))
        answer_identifiers = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", answer))
        references_code = bool(code_identifiers & answer_identifiers)
        big_o = bool(re.search(r"\b(?:time|space|complexity)\b[^.?!]{0,50}\bO\s*\([^)]*\)", text))
        edge_reasoning = bool(re.search(r"\b(?:handle|consider|check|when)\b[^.?!]{0,45}\b(?:empty|null|duplicate|boundary|edge)\b", text))
        technical = 6 if coherent else 4
        technical += 1 if references_code else 0
        complexity = 7 if coherent and big_o else 4
        edge = 7 if coherent and edge_reasoning else 4
        communication = min(7, 4 + (1 if coherent else 0) + (1 if len(sentences) >= 2 else 0))
        confidence = 6 if coherent and not any(x in text for x in ("maybe", "i think", "not sure")) else 4
        return Evaluation(technical_accuracy=technical, communication=communication,
                          complexity_understanding=complexity, edge_case_reasoning=edge,
                          confidence=confidence,
                          feedback="Fallback heuristic: structured reasoning detected, but connect claims to the submitted code." if coherent else "Fallback heuristic: answer needs a coherent explanation grounded in the submitted code.")
