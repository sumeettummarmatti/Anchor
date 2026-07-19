import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.project import LearningSession
from app.models.hint_event import HintEvent

async def run():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(LearningSession).order_by(LearningSession.started_at.desc()).limit(1))
        ls = res.scalar_one_or_none()
        print(f"Fixing session {ls.id}")
        
        # Add 20 fake hints to blow the hint rate out of the water
        for _ in range(20):
            hint = HintEvent(
                user_id=ls.user_id,
                session_id=ls.id,
                level=1,
                prompt="fake",
                response="fake"
            )
            session.add(hint)
        await session.commit()
        print("Done!")

asyncio.run(run())
