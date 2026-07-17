from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hint_event import HintEvent


class HintRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def highest_level(self, user_id: UUID, session_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(HintEvent.level)).where(
                HintEvent.user_id == user_id, HintEvent.session_id == session_id
            )
        )
        return result.scalar_one() or 0

    async def create(self, event: HintEvent) -> HintEvent:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
