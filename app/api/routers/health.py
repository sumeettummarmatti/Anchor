from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="API liveness check")
async def health_check(settings: Settings = get_settings()) -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC),
        environment=settings.environment,
    )
