from fastapi.testclient import TestClient

from interview_engine.app.analytics.repositories.analytics_repository import InMemoryAnalyticsRepository
from interview_engine.app.analytics.routers.analytics import create_router
from interview_engine.app.analytics.services.event_processor import EventProcessor
from fastapi import FastAPI


def build_analytics_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(create_router(EventProcessor(InMemoryAnalyticsRepository())))
    return app


def test_analytics_event_ingestion_is_authenticated_and_user_scoped():
    client = TestClient(build_analytics_test_app())
    headers = {"X-API-Key": "dev-api-key", "X-User-ID": "analytics-user"}

    response = client.post(
        "/analytics/events",
        json={"event_type": "TRACE_CREATED", "source": "visualization", "metadata": {"trace_id": "t-1"}},
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == "analytics-user"
    assert response.json()["event_type"] == "TRACE_CREATED"
    assert client.post("/analytics/events", json={"event_type": "TRACE_CREATED", "source": "visualization"}).status_code == 401


def test_analytics_event_ingestion_rejects_unknown_event_type():
    client = TestClient(build_analytics_test_app())
    response = client.post(
        "/analytics/events",
        json={"event_type": "UNKNOWN", "source": "test"},
        headers={"X-API-Key": "dev-api-key", "X-User-ID": "analytics-user"},
    )

    assert response.status_code == 400
