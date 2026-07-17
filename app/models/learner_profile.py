from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    hint_depth_ceiling: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    teaching_style: Mapped[str] = mapped_column(String(32), default="socratic", nullable=False)
    difficulty_adjustment: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    intervention_frequency: Mapped[float] = mapped_column(Float, default=0.35, nullable=False)
    rolling_hint_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rolling_failed_run_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rolling_avg_solve_time_seconds: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    sessions_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
