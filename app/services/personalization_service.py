"""Learner adaptation context and profile update rules for Phase 7."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent
from app.models.learner_profile import LearnerProfile
from app.models.project import LearningSession
from app.repositories.learner_profile_repository import LearnerProfileRepository


@dataclass(frozen=True)
class AdaptationContext:
    """Small, serializable set of learner signals used by mentor prompts."""

    hint_depth_ceiling: int
    teaching_style: str
    difficulty_adjustment: float
    intervention_frequency: float
    rolling_hint_rate: float
    rolling_failed_run_ratio: float
    rolling_avg_solve_time_seconds: float

    @classmethod
    def from_profile(cls, profile: LearnerProfile) -> AdaptationContext:
        return cls(
            hint_depth_ceiling=profile.hint_depth_ceiling,
            teaching_style=profile.teaching_style,
            difficulty_adjustment=profile.difficulty_adjustment,
            intervention_frequency=profile.intervention_frequency,
            rolling_hint_rate=profile.rolling_hint_rate,
            rolling_failed_run_ratio=profile.rolling_failed_run_ratio,
            rolling_avg_solve_time_seconds=profile.rolling_avg_solve_time_seconds,
        )


class PersonalizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profiles = LearnerProfileRepository(session)

    async def ensure_profile(self, user_id: UUID, *, commit: bool = True) -> LearnerProfile:
        profile = await self.profiles.get_by_user(user_id)
        if profile is not None:
            return profile
        return await self.profiles.create(user_id, commit=commit)

    async def get_context(self, user_id: UUID) -> AdaptationContext:
        profile = await self.ensure_profile(user_id)
        return AdaptationContext.from_profile(profile)

    async def update_after_session(self, user_id: UUID) -> LearnerProfile:
        profile = await self.ensure_profile(user_id)
        runs_result = await self.session.execute(
            select(ExecutionRun)
            .join(LearningSession, ExecutionRun.session_id == LearningSession.id)
            .where(LearningSession.user_id == user_id)
        )
        runs = list(runs_result.scalars())
        hints_result = await self.session.execute(
            select(HintEvent).where(HintEvent.user_id == user_id)
        )
        hints = list(hints_result.scalars())
        sessions_result = await self.session.execute(
            select(LearningSession).where(
                LearningSession.user_id == user_id,
                LearningSession.ended_at.is_not(None),
            )
        )
        completed_sessions = len(list(sessions_result.scalars()))

        run_count = len(runs)
        failed_ratio = sum(run.status != "completed" for run in runs) / max(run_count, 1)
        hint_rate = len(hints) / max(run_count, 1)
        difficulty_adjustment = max(-1.0, min(1.0, round((0.5 - failed_ratio) * 0.8, 3)))
        if failed_ratio >= 0.5:
            teaching_style = "scaffolded"
        elif hint_rate >= 1.5:
            teaching_style = "encouraging"
        else:
            teaching_style = "socratic"
        intervention_frequency = max(
            0.2, min(1.0, round(0.2 + failed_ratio * 0.6 + min(hint_rate, 2.0) * 0.1, 3))
        )
        hint_ceiling = 3 if failed_ratio >= 0.7 else 4 if hint_rate >= 1.5 else 5

        profile.hint_depth_ceiling = hint_ceiling
        profile.teaching_style = teaching_style
        profile.difficulty_adjustment = difficulty_adjustment
        profile.intervention_frequency = intervention_frequency
        profile.rolling_hint_rate = round(hint_rate, 3)
        profile.rolling_failed_run_ratio = round(failed_ratio, 3)
        profile.sessions_completed = completed_sessions
        profile.execution_runs = run_count
        profile.hints_used = len(hints)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile


async def update_profile_after_session(user_id: UUID) -> None:
    """Background-task entry point with an independent database session."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await PersonalizationService(session).update_after_session(user_id)
