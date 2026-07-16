from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import session as db_session
from app.db.base import Base
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def test_database() -> AsyncGenerator[None, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
    )
    old_engine = db_session.engine
    old_session_factory = db_session.AsyncSessionLocal
    db_session.engine = engine
    db_session.AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    db_session.engine = old_engine
    db_session.AsyncSessionLocal = old_session_factory


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
