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
)
from app.services.mentor_service import MentorService

router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.post("/chat", response_model=MentorResponse)
async def chat(
    payload: MentorChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> MentorResponse:
    message, model = await MentorService(session, settings).chat(current_user.id, payload)
    return MentorResponse(message=message, model=model)


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
    return MentorResponse(message=message, model=model)
