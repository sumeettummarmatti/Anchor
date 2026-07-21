from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ai_service import AIService


async def test_health_check_returns_service_metadata() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["environment"] == "development"
    assert "timestamp" in payload


async def test_health_check_provides_request_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"X-Request-ID": "test-request"})

    assert response.headers["X-Request-ID"] == "test-request"


async def test_demo_ui_is_served() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/demo/")

    assert response.status_code == 200
    assert "A focused workspace to practice coding" in response.text
    assert 'id="llm-status"' in response.text


async def test_llm_health_reports_unavailable(monkeypatch) -> None:
    async def unavailable(self: AIService):
        return False, None, None, "ollama: unavailable; lmstudio: unavailable"

    monkeypatch.setattr(AIService, "probe", unavailable)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/llm")

    assert response.status_code == 200
    assert response.json() == {
        "status": "unavailable",
        "provider": None,
        "model": None,
        "detail": "ollama: unavailable; lmstudio: unavailable",
    }
