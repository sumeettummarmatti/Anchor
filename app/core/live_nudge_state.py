"""Redis-backed suppression and fixed-window rate limiting for Live Tutor."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.exceptions import RateLimitError

# Keep a short cooldown after dismissal so an accidental click does not mute
# the live tutor for the rest of a work session.
DISMISSED_LOCK_MINUTES = 2
POST_SOLVE_STAGE = "solved"
_redis: Redis | None = None


async def get_redis() -> Redis:
    """Return the process-local Redis client used by live-nudge state."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _state_key(session_id: UUID) -> str:
    return f"live_nudge:{session_id}"


async def get_nudge_state(session_id: UUID) -> dict[str, str]:
    redis = await get_redis()
    raw_state = await redis.hgetall(_state_key(session_id))
    return {
        (key.decode() if isinstance(key, bytes) else str(key)): (
            value.decode() if isinstance(value, bytes) else str(value)
        )
        for key, value in raw_state.items()
    }


async def should_suppress_pretrigger(session_id: UUID) -> bool:
    """Check locks that are known before asking the model to classify the stage."""
    state = await get_nudge_state(session_id)
    dismissed_until = state.get("dismissed_until")
    if dismissed_until:
        try:
            if time.time() < float(dismissed_until):
                return True
        except ValueError:
            pass
    return state.get("last_stage") == POST_SOLVE_STAGE


async def should_suppress_posttrigger(session_id: UUID, actual_stage: str) -> bool:
    """Suppress a repeated stage only during its short cooldown window."""
    state = await get_nudge_state(session_id)
    if state.get("last_stage") != actual_stage:
        return False
    last_ts_raw = state.get("last_nudge_ts")
    if not last_ts_raw:
        return False
    try:
        return time.time() - float(last_ts_raw) < 4.0
    except ValueError:
        return False


async def record_nudge(session_id: UUID, stage: str) -> None:
    redis = await get_redis()
    key = _state_key(session_id)
    state = await get_nudge_state(session_id)
    count = int(state.get("nudge_count", "0")) + 1
    await redis.hset(
        key,
        mapping={
            "last_stage": stage,
            "last_nudge_ts": str(time.time()),
            "nudge_count": str(count),
        },
    )


async def set_dismissed(session_id: UUID) -> None:
    redis = await get_redis()
    dismissed_until = datetime.now(UTC) + timedelta(minutes=DISMISSED_LOCK_MINUTES)
    await redis.hset(_state_key(session_id), "dismissed_until", str(dismissed_until.timestamp()))


async def check_rate_limit(
    user_id: UUID,
    session_id: UUID,
    *,
    limit: int = 40,
    window_seconds: int = 60,
) -> None:
    """Apply a fixed-window Redis counter for live-nudge calls."""
    redis = await get_redis()
    key = f"live_nudge_rl:{user_id}:{session_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        raise RateLimitError("Too many live tutor nudges. Try again shortly.")
