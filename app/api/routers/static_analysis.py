"""Static-analysis endpoints."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.static_analysis import StaticAnalysisRequest, StaticAnalysisResult
from app.services.static_analysis_service import StaticAnalysisService

router = APIRouter(prefix="/static-analysis", tags=["static analysis"])


@router.post("/run", response_model=StaticAnalysisResult)
async def run_static_analysis(
    payload: StaticAnalysisRequest,
    _: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> StaticAnalysisResult:
    return await StaticAnalysisService(settings).analyze(payload.language, payload.code)
