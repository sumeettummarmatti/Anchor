from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse, LLMHealthResponse
from app.services.ai_service import AIService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="API liveness check")
async def health_check(settings: Settings = get_settings()) -> HealthResponse:
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC),
        environment=settings.environment,
    )


@router.get("/health/llm", response_model=LLMHealthResponse, summary="LLM provider readiness")
async def llm_health(settings: Settings = get_settings()) -> LLMHealthResponse:
    """Check whether a configured provider has a reachable loaded model."""
    available, provider, model, detail = await AIService(settings).probe()
    return LLMHealthResponse(
        status="ok" if available else "unavailable",
        provider=provider,
        model=model,
        detail=detail,
    )
