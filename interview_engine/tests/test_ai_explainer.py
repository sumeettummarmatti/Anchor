from interview_engine.app.visualization.models.execution_trace import ExecutionStep
from interview_engine.app.visualization.services.ai_explainer import AIExplainer

def test_ai_explainer_returns_structured_annotation():
    step = ExecutionStep("t1", 1, 1, "total = 1", "LINE_EXECUTED", {"total": 1}, {}, ["<module>"], "")
    annotation = AIExplainer().explain("t1", step)
    assert annotation.trace_id == "t1"
    assert annotation.detected_concept == "variable assignment"
    assert annotation.explanation
