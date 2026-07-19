import asyncio
from uuid import uuid4
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.session import AsyncSessionLocal
from app.services.stuck_detection_service import check_stuck_score, get_stuck_score
from app.models.project import LearningSession
from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent

async def run():
    async with AsyncSessionLocal() as session:
        # Get the latest session
        res = await session.execute(select(LearningSession).order_by(LearningSession.started_at.desc()).limit(1))
        ls = res.scalar_one_or_none()
        if not ls:
            print("No learning sessions found.")
            return
            
        print(f"Using session: {ls.id}")
        score = await get_stuck_score(session, ls.id)
        print("Score:", score.score)
        print("Is Stuck:", score.is_stuck)
        print("Signals:", score.signals)

asyncio.run(run())
