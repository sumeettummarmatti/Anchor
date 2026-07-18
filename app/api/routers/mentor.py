from dataclasses import asdict
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.live_nudge import LiveNudgeFeedback, LiveNudgeRequest, LiveNudgeResponse
from app.schemas.mentor import (
    ExplainErrorRequest,
    HintResponse,
    MentorChatRequest,
    MentorHintRequest,
    MentorResponse,
    PersonalizationSummary,
)
from app.services.ai_service import AIService
from app.services.mentor_service import MentorService
from app.services.personalization_service import PersonalizationService
from app.services.session_service import SessionService

logger = structlog.get_logger(__name__)


async def _personalization_summary(session: AsyncSession, user_id: UUID) -> PersonalizationSummary:
    context = await PersonalizationService(session).get_context(user_id)
    return PersonalizationSummary.model_validate(asdict(context))


router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.post("/chat", response_model=MentorResponse)
async def chat(
    payload: MentorChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MentorResponse:
    message, model = await MentorService(session, settings).chat(current_user.id, payload)
    return MentorResponse(
        message=message,
        model=model,
        personalization=await _personalization_summary(session, current_user.id),
    )


@router.post("/hint", response_model=HintResponse)
async def hint(
    payload: MentorHintRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> HintResponse:
    event, model = await MentorService(session, settings).hint(current_user.id, payload)
    return HintResponse(
        message=event.response,
        model=model,
        personalization=await _personalization_summary(session, current_user.id),
        hint_id=event.id,
        level=event.level,
        created_at=event.created_at,
    )


@router.post("/explain-error", response_model=MentorResponse)
async def explain_error(
    payload: ExplainErrorRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MentorResponse:
    message, model = await MentorService(session, settings).explain_error(current_user.id, payload)
    return MentorResponse(
        message=message,
        model=model,
        personalization=await _personalization_summary(session, current_user.id),
    )


@router.post("/live-nudge", response_model=LiveNudgeResponse)
async def live_nudge(
    payload: LiveNudgeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LiveNudgeResponse:
    try:
        adaptation = await PersonalizationService(session).get_context(current_user.id)
    except Exception:
        logger.warning("live_nudge_profile_fallback", user_id=str(current_user.id))
        from app.services.personalization_service import AdaptationContext

        adaptation = AdaptationContext(
            hint_depth_ceiling=3,
            teaching_style="socratic",
            difficulty_adjustment=0.0,
            intervention_frequency=0.35,
            rolling_hint_rate=0.0,
            rolling_failed_run_ratio=0.0,
            rolling_avg_solve_time_seconds=0.0,
        )
    await SessionService(session).get(payload.session_id, current_user.id)
    return await AIService(settings).live_nudge(
        payload, adaptation, session=session, user_id=current_user.id
    )


@router.post("/live-nudge/feedback", status_code=204)
async def live_nudge_feedback(
    payload: LiveNudgeFeedback,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await SessionService(session).get(payload.session_id, current_user.id)
    if not payload.helpful:
        from app.core.live_nudge_state import set_dismissed

        await set_dismissed(payload.session_id)
