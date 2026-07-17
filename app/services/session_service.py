from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.project import LearningSession
from app.repositories.project_repository import ProjectRepository
from app.services.personalization_service import PersonalizationService
from app.services.project_service import ProjectService


class SessionService:
    _event_requests: dict[UUID, deque[float]] = defaultdict(deque)
    max_batches_per_minute = 20

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectRepository(session)

    async def start(self, user_id: UUID, project_id: UUID) -> LearningSession:
        await ProjectService(self.session).get(project_id, user_id)
        learning_session = LearningSession(user_id=user_id, project_id=project_id)
        self.session.add(learning_session)
        await PersonalizationService(self.session).ensure_profile(user_id, commit=False)
        await self.session.commit()
        await self.session.refresh(learning_session)
        return learning_session

    async def get(self, session_id: UUID, user_id: UUID) -> LearningSession:
        learning_session = await self.projects.get_session(session_id, user_id)
        if learning_session is None:
            raise NotFoundError("Session not found.")
        return learning_session

    async def append_events(
        self, session_id: UUID, user_id: UUID, events: list[dict[str, object]]
    ) -> LearningSession:
        now = monotonic()
        recent = self._event_requests[session_id]
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= self.max_batches_per_minute:
            from app.core.exceptions import RateLimitError

            raise RateLimitError("Too many event batches for this session. Try again shortly.")
        recent.append(now)
        learning_session = await self.get(session_id, user_id)
        learning_session.editor_event_log = [*learning_session.editor_event_log, *events][-500:]
        await self.session.commit()
        await self.session.refresh(learning_session)
        return learning_session

    async def end(self, session_id: UUID, user_id: UUID) -> LearningSession:
        learning_session = await self.get(session_id, user_id)
        learning_session.ended_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(learning_session)
        return learning_session
