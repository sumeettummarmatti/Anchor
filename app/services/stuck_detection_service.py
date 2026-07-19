"""Phase 8 stuck-score service boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent
from app.models.project import LearningSession


@dataclass(frozen=True)
class StuckScore:
    score: float
    is_stuck: bool
    signals: dict[str, float]


def compute_stuck_score(
    events: list[dict], runs: list[ExecutionRun], hints: list[HintEvent], now: datetime
) -> StuckScore:
    """Pure, synchronous calculation of a learner's stuck score."""
    # 1. Consecutive failed runs
    failed_streak = 0
    for run in reversed(runs):
        if run.status != "completed":
            failed_streak += 1
        else:
            break
    sig_failures = min(failed_streak / 3.0, 1.0)

    # 2. Hint rate (hints per run)
    run_count = len(runs)
    hint_rate = len(hints) / max(run_count, 1)
    sig_hints = min(hint_rate / 2.0, 1.0)

    # 3. Inactivity gap
    # If the most recent event has a long typing_pause_ms, they might be stuck.
    last_pause_ms = events[-1].get("typing_pause_ms") or 0 if events else 0
    sig_inactivity = min(last_pause_ms / 60_000.0, 1.0)  # max out at 60s pause

    # 4. Repeated edits without progress
    # Check if the last N events are in the same file/function, and we have a failed streak
    sig_edits = 0.0
    if len(events) >= 5 and failed_streak > 0:
        recent = events[-5:]
        first_func = recent[0].get("current_function")
        first_file = recent[0].get("open_file")
        if first_file and all(
            e.get("current_function") == first_func and e.get("open_file") == first_file
            for e in recent
        ):
            sig_edits = 1.0

    signals = {
        "consecutive_failures": round(sig_failures, 3),
        "hint_rate": round(sig_hints, 3),
        "inactivity": round(sig_inactivity, 3),
        "repeated_edits": round(sig_edits, 3),
    }

    # Simple unweighted average of the signals
    score = sum(signals.values()) / len(signals)

    # Threshold for being "stuck": 0.25 requires at least one strong signal or multiple weak ones.
    is_stuck = score >= 0.25

    return StuckScore(
        score=round(score, 3),
        is_stuck=is_stuck,
        signals=signals,
    )


async def check_stuck_score(session_id: UUID) -> None:
    """Background task to compute stuck score. Purely to align with event ingestion lifecycle."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await get_stuck_score(db, session_id)


async def get_stuck_score(db: AsyncSession, session_id: UUID) -> StuckScore:
    """Load session data and compute stuck score."""
    result = await db.execute(select(LearningSession).where(LearningSession.id == session_id))
    learning_session = result.scalar_one_or_none()
    if not learning_session:
        raise NotFoundError("Session not found.")

    runs_result = await db.execute(
        select(ExecutionRun)
        .where(ExecutionRun.session_id == session_id)
        .order_by(ExecutionRun.created_at.asc())
    )
    runs = list(runs_result.scalars())

    hints_result = await db.execute(
        select(HintEvent)
        .where(HintEvent.session_id == session_id)
        .order_by(HintEvent.created_at.asc())
    )
    hints = list(hints_result.scalars())

    return compute_stuck_score(
        learning_session.editor_event_log, runs, hints, datetime.now(UTC)
    )
