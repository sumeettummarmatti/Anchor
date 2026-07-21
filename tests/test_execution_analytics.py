from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.schemas.execution import ExecutionRequest
from app.schemas.static_analysis import StaticAnalysisResult
from app.services.execution_service import ExecutionService


class FakeSession:
    def add(self, execution) -> None:
        self.execution = execution

    async def commit(self) -> None:
        return None

    async def refresh(self, execution) -> None:
        return None


class FakeResponse:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, dict[str, object]]:
        return {
            "run": {
                "code": self.exit_code,
                "stdout": "",
                "stderr": "",
                "output": "",
                "wall_time": 1,
            }
        }


class FakeAsyncClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def post(self, *args, **kwargs) -> FakeResponse:
        return self.response


@pytest.mark.parametrize(
    ("exit_code", "expected_status", "should_publish"),
    [(0, "completed", True), (1, "failed", False)],
)
async def test_execution_publishes_problem_solved_only_for_success(
    monkeypatch, exit_code: int, expected_status: str, should_publish: bool
) -> None:
    publisher = MagicMock()

    async def fake_analyze(self, language, code):
        return StaticAnalysisResult(language=language, analyzer="test", available=False)

    monkeypatch.setattr(
        "app.services.execution_service.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(FakeResponse(exit_code)),
    )
    monkeypatch.setattr(
        "app.services.static_analysis_service.StaticAnalysisService.analyze",
        fake_analyze,
    )
    monkeypatch.setattr(
        "interview_engine.app.main.get_analytics_event_publisher",
        lambda: publisher,
    )

    request = ExecutionRequest(code="print('ok')", language="python")
    execution, _, _ = await ExecutionService(FakeSession(), Settings()).run("user-1", request)

    assert execution.status == expected_status
    if should_publish:
        publisher.publish.assert_called_once_with(
            event_type="PROBLEM_SOLVED",
            source="execution",
            user_id="user-1",
            metadata={"language": "python", "session_id": None},
        )
    else:
        publisher.publish.assert_not_called()
