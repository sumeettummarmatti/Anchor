from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient
from sqlalchemy import select

from app.core import live_nudge_state
from app.core.exceptions import RateLimitError
from app.db import session as db_session
from app.models.hint_event import HintEvent
from app.prompt_templates import live_nudge
from app.services.ai_service import AIService, PromptContext
from app.services.personalization_service import AdaptationContext
from tests.test_projects import token_for


@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(live_nudge_state, "get_redis", lambda: redis)
    yield redis
    await redis.aclose()


async def _workspace(client: AsyncClient, email: str) -> tuple[dict[str, str], str]:
    tokens = await token_for(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    project = await client.post(
        "/projects", headers=headers, json={"name": "Live Tutor", "language": "python"}
    )
    session = await client.post(
        "/sessions", headers=headers, json={"project_id": project.json()["id"]}
    )
    return headers, session.json()["id"]


async def test_suppression_checks_real_stage_only(fake_redis) -> None:
    session_id = uuid4()
    await live_nudge_state.record_nudge(session_id, "exploring")
    assert await live_nudge_state.should_suppress_pretrigger(session_id) is False
    assert await live_nudge_state.should_suppress_posttrigger(session_id, "pinpoint") is False
    assert await live_nudge_state.should_suppress_posttrigger(session_id, "exploring") is True


async def test_same_stage_is_allowed_after_cooldown(fake_redis) -> None:
    session_id = uuid4()
    await fake_redis.hset(
        f"live_nudge:{session_id}",
        mapping={"last_stage": "exploring", "last_nudge_ts": str(time.time() - 5)},
    )
    assert await live_nudge_state.should_suppress_posttrigger(session_id, "exploring") is False


async def test_dismissed_and_solved_states_suppress_pretrigger(fake_redis) -> None:
    dismissed_session = uuid4()
    await live_nudge_state.set_dismissed(dismissed_session)
    assert await live_nudge_state.should_suppress_pretrigger(dismissed_session) is True

    solved_session = uuid4()
    await live_nudge_state.record_nudge(solved_session, live_nudge_state.POST_SOLVE_STAGE)
    assert await live_nudge_state.should_suppress_pretrigger(solved_session) is True


async def test_live_nudge_rate_limit_raises(fake_redis) -> None:
    user_id, session_id = uuid4(), uuid4()
    await live_nudge_state.check_rate_limit(user_id, session_id, limit=2)
    await live_nudge_state.check_rate_limit(user_id, session_id, limit=2)
    with pytest.raises(RateLimitError):
        await live_nudge_state.check_rate_limit(user_id, session_id, limit=2)


def test_live_nudge_prompt_contains_constraints_and_adaptation() -> None:
    adaptation = AdaptationContext(
        hint_depth_ceiling=2,
        teaching_style="scaffolded",
        difficulty_adjustment=-0.2,
        intervention_frequency=0.7,
        rolling_hint_rate=1.0,
        rolling_failed_run_ratio=0.8,
        rolling_avg_solve_time_seconds=10.0,
    )
    system, user = live_nudge.build(
        PromptContext(
            "live_nudge", "python", "def solve(): pass", "idle_800ms", adaptation=adaptation
        )
    )
    assert "at most 2 sentences" in system
    assert "scaffolding" in system
    assert "idle_800ms" in user


def test_live_nudge_parser_accepts_lmstudio_markdown_json() -> None:
    parsed = AIService._parse_live_nudge_json(
        '```json\n{"nudge":"Check the loop condition.",'
        '"nudge_type":"pinpoint","stage":"exploring"}\n```'
    )
    assert parsed["nudge"] == "Check the loop condition."


async def test_live_nudge_plain_text_fallback_is_displayed(
    client: AsyncClient, monkeypatch, fake_redis
) -> None:
    headers, session_id = await _workspace(client, "live-nudge-plain-text@example.com")

    async def fake_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        return (
            "<think>reasoning omitted</think>Check the loop condition. "
            "This is extra explanation.",
            "test-model",
        )

    monkeypatch.setattr(AIService, "complete", fake_complete)
    response = await client.post(
        "/mentor/live-nudge",
        headers=headers,
        json={"session_id": session_id, "language": "python", "code": "for x in items:"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "nudge": "Check the loop condition",
        "nudge_type": "encourage",
        "stage": "exploring",
        "should_display": True,
    }


async def test_live_nudge_happy_path_persists_source(
    client: AsyncClient, monkeypatch, fake_redis
) -> None:
    headers, session_id = await _workspace(client, "live-nudge-happy@example.com")

    async def fake_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        assert context.intent == "live_nudge"
        assert context.adaptation is not None
        return (
            '{"nudge":"What does this loop need to track?",'
            '"nudge_type":"scaffold","stage":"exploring"}',
            "test-model",
        )

    monkeypatch.setattr(AIService, "complete", fake_complete)
    response = await client.post(
        "/mentor/live-nudge",
        headers=headers,
        json={"session_id": session_id, "language": "python", "code": "for x in items:"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "nudge": "What does this loop need to track?",
        "nudge_type": "scaffold",
        "stage": "exploring",
        "should_display": True,
    }
    async with db_session.AsyncSessionLocal() as session:
        event = await session.scalar(
            select(HintEvent).where(HintEvent.session_id == UUID(session_id))
        )
        assert event is not None
        assert event.source == "nudge"


async def test_live_nudge_same_stage_suppresses_after_classification(
    client: AsyncClient, monkeypatch, fake_redis
) -> None:
    headers, session_id = await _workspace(client, "live-nudge-suppressed@example.com")
    parsed_session_id = UUID(session_id)
    await live_nudge_state.record_nudge(parsed_session_id, "exploring")
    called = False

    async def same_stage_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        nonlocal called
        called = True
        return (
            '{"nudge":"same stage","nudge_type":"encourage",'
            '"stage":"exploring"}',
            "test-model",
        )

    monkeypatch.setattr(AIService, "complete", same_stage_complete)
    response = await client.post(
        "/mentor/live-nudge",
        headers=headers,
        json={"session_id": session_id, "language": "python", "code": "x = 1"},
    )
    assert response.status_code == 200
    assert response.json()["should_display"] is False
    assert called is True


async def test_live_nudge_dismissed_suppresses_before_llm(
    client: AsyncClient, monkeypatch, fake_redis
) -> None:
    headers, session_id = await _workspace(client, "live-nudge-dismissed@example.com")
    await live_nudge_state.set_dismissed(UUID(session_id))
    called = False

    async def fail_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        nonlocal called
        called = True
        raise AssertionError("dismissed nudge must not call the model")

    monkeypatch.setattr(AIService, "complete", fail_complete)
    response = await client.post(
        "/mentor/live-nudge",
        headers=headers,
        json={"session_id": session_id, "language": "python", "code": "x = 1"},
    )
    assert response.status_code == 200
    assert response.json()["should_display"] is False
    assert called is False


async def test_feedback_sets_dismissed_lock(client: AsyncClient, fake_redis) -> None:
    headers, session_id = await _workspace(client, "live-nudge-feedback@example.com")
    response = await client.post(
        "/mentor/live-nudge/feedback",
        headers=headers,
        json={"session_id": session_id, "helpful": False},
    )
    assert response.status_code == 204
    assert await live_nudge_state.should_suppress_pretrigger(UUID(session_id))
