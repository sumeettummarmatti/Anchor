from interview_engine.app.interview.services.evaluator import Evaluator

def test_fallback_evaluator_does_not_reward_keyword_stuffing():
    answer = ("complexity edge boundary duplicate null O(n) O(1) " * 30).strip()
    result = Evaluator().evaluate("Explain the approach", answer, {"code": "def solve(nums): return nums"})
    assert max(result.technical_accuracy, result.communication, result.complexity_understanding, result.edge_case_reasoning, result.confidence) < 8
    assert "fallback heuristic" in result.feedback.lower()
