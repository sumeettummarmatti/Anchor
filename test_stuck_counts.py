import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.project import LearningSession
from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent

async def run():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(LearningSession).order_by(LearningSession.started_at.desc()).limit(1))
        ls = res.scalar_one_or_none()
        runs = await session.execute(select(ExecutionRun).where(ExecutionRun.session_id == ls.id))
        hints = await session.execute(select(HintEvent).where(HintEvent.session_id == ls.id))
        print(f"Runs: {len(list(runs.scalars()))}")
        print(f"Hints: {len(list(hints.scalars()))}")

asyncio.run(run())
