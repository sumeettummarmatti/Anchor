from httpx import ASGITransport, AsyncClient

from app.main import app


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
    assert "Meet your coding mentor" in response.text
