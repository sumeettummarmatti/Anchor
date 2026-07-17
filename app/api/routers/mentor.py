from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.mentor import (
    ExplainErrorRequest,
    HintResponse,
    MentorChatRequest,
    MentorHintRequest,
    MentorResponse,
    PersonalizationSummary,
)
from app.services.mentor_service import MentorService
from app.services.personalization_service import PersonalizationService


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
