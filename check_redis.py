import asyncio
from app.core.live_nudge_state import get_nudge_state, should_suppress_pretrigger
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.project import LearningSession
from uuid import UUID

async def run():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(LearningSession).order_by(LearningSession.started_at.desc()).limit(1))
        ls = res.scalar_one_or_none()
        state = await get_nudge_state(ls.id)
        suppressed = await should_suppress_pretrigger(ls.id)
        print("Suppressed:", suppressed)
        print("State:", state)

asyncio.run(run())
