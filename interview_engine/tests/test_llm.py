import json
import logging
import pytest
from interview_engine.app.core.llm import LLMResponseError, LLMTransientError, complete_json_with_retry
from interview_engine.app.interview.services.evaluator import Evaluator

class TimeoutLLM:
    def __init__(self): self.calls = 0
    def complete_json(self, system, user):
        self.calls += 1
        raise TimeoutError("simulated timeout")

class InvalidJsonLLM:
    def complete_json(self, system, user):
        raise json.JSONDecodeError("bad json", "{", 0)

class ValidEvaluatorLLM:
    def complete_json(self, system, user):
        return {"technical_accuracy": 9, "communication": 8, "complexity_understanding": 8, "edge_case_reasoning": 7, "confidence": 8, "feedback": "specific"}

class RepairingEvaluatorLLM:
    def __init__(self): self.calls = 0
    def complete_json(self, system, user):
        self.calls += 1
        if self.calls == 1: return {"technical_accuracy": 9}
        return {"technical_accuracy": 9, "communication": 8, "complexity_understanding": 8, "edge_case_reasoning": 7, "confidence": 8, "feedback": "repaired"}

def test_llm_timeout_retries_once_and_logs(caplog):
    client = TimeoutLLM()
    with caplog.at_level(logging.WARNING), pytest.raises(LLMTransientError):
        complete_json_with_retry(client, "system", "user", "test")
    assert client.calls == 2
    assert "LLM transient failure" in caplog.text

def test_invalid_json_logs_distinct_failure(caplog):
    with caplog.at_level(logging.ERROR), pytest.raises(LLMResponseError):
        complete_json_with_retry(InvalidJsonLLM(), "system", "user", "test")
    assert "LLM response/schema failure" in caplog.text

def test_llm_evaluation_marks_provider():
    result = Evaluator(ValidEvaluatorLLM()).evaluate("Explain", "A detailed answer", {})
    assert result.provider_used == "llm"

def test_invalid_evaluation_is_repaired_before_fallback():
    client = RepairingEvaluatorLLM()
    result = Evaluator(client).evaluate("Explain", "A detailed answer", {})
    assert client.calls == 2
    assert result.feedback == "repaired"
    assert result.provider_used == "llm"
