from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.project import LearningSession
from app.models.user import User
from app.schemas.sessions import EventBatch, SessionCreate, SessionResponse
from app.services.personalization_service import update_profile_after_session
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def response(session: LearningSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        project_id=session.project_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        event_count=len(session.editor_event_log),
    )


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    payload: SessionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    return response(await SessionService(session).start(current_user.id, payload.project_id))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    return response(await SessionService(session).get(session_id, current_user.id))


@router.post("/{session_id}/events", response_model=SessionResponse)
async def ingest_events(
    session_id: UUID,
    payload: EventBatch,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    events = [event.model_dump() for event in payload.events]
    return response(
        await SessionService(session).append_events(session_id, current_user.id, events)
    )


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    result = await SessionService(session).end(session_id, current_user.id)
    background_tasks.add_task(update_profile_after_session, current_user.id)
    return response(result)
