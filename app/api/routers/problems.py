from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.problems import ProblemDetail, ProblemRecommendation
from app.services.problem_sources import ProblemSourceService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("/recommended", response_model=list[ProblemRecommendation])
async def recommended_problems(
    k: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[ProblemRecommendation]:
    return await RecommendationService(
        session, artifact_dir=settings.recommendation_artifact_dir
    ).get_recommendations(current_user.id, k=k)


@router.get("/details/{problem_id}", response_model=ProblemDetail)
async def problem_details(
    problem_id: str,
    _: User = Depends(get_current_user),
) -> ProblemDetail:
    try:
        detail = await ProblemSourceService().fetch_details(problem_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail="Problem details were not found for this recommendation."
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="The problem source is unavailable right now.") from exc
    return ProblemDetail.model_validate(detail)
