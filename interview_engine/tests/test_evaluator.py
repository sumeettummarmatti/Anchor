from interview_engine.app.interview.services.evaluator import Evaluator


class AllZeroEvaluatorLLM:
    def __init__(self): self.calls = 0
    def complete_json(self, system, user):
        self.calls += 1
        return {"technical_accuracy": 0, "communication": 0, "complexity_understanding": 0, "edge_case_reasoning": 0, "confidence": 0, "feedback": "zero"}

def test_fallback_evaluator_does_not_reward_keyword_stuffing():
    answer = ("complexity edge boundary duplicate null O(n) O(1) " * 30).strip()
    result = Evaluator().evaluate("Explain the approach", answer, {"code": "def solve(nums): return nums"})
    assert max(result.technical_accuracy, result.communication, result.complexity_understanding, result.edge_case_reasoning, result.confidence) < 8
    assert "fallback heuristic" in result.feedback.lower()


def test_explicit_no_knowledge_answer_is_the_only_all_zero_scorecard():
    result = Evaluator().evaluate("Explain the approach", "I don't know.", {"code": ""})
    assert result.technical_accuracy == result.communication == 0


def test_non_empty_answer_is_reassessed_when_model_returns_all_zero_scores():
    client = AllZeroEvaluatorLLM()
    result = Evaluator(client).evaluate("Explain the approach", "I would use a hash map to store values as I iterate.", {"code": ""})
    assert client.calls == 2
    assert not all(score == 0 for score in (result.technical_accuracy, result.communication, result.complexity_understanding, result.edge_case_reasoning, result.confidence))
