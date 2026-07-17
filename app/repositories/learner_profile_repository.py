from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learner_profile import LearnerProfile


class LearnerProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user(self, user_id: UUID) -> LearnerProfile | None:
        result = await self.session.execute(
            select(LearnerProfile).where(LearnerProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: UUID, *, commit: bool = True) -> LearnerProfile:
        profile = LearnerProfile(user_id=user_id)
        self.session.add(profile)
        if commit:
            await self.session.commit()
            await self.session.refresh(profile)
        else:
            await self.session.flush()
        return profile
