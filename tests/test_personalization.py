from uuid import UUID

from httpx import AsyncClient

from app.db import session as db_session
from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent
from app.services.personalization_service import PersonalizationService
from tests.test_projects import token_for


async def _workspace(client: AsyncClient, email: str) -> tuple[dict[str, str], str]:
    tokens = await token_for(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    project = await client.post(
        "/projects", headers=headers, json={"name": "Profile test", "language": "python"}
    )
    session = await client.post(
        "/sessions", headers=headers, json={"project_id": project.json()["id"]}
    )
    return headers, session.json()["id"]


async def test_profile_is_auto_created_on_first_session(client: AsyncClient) -> None:
    headers, session_id = await _workspace(client, "profile-create@example.com")
    profile = await client.get("/users/me/profile", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["user_id"]
    assert body["hint_depth_ceiling"] == 5
    assert body["teaching_style"] == "socratic"
    assert body["sessions_completed"] == 0
    assert session_id


async def test_profile_updates_after_session_end(client: AsyncClient) -> None:
    headers, session_id = await _workspace(client, "profile-update@example.com")
    ended = await client.post(f"/sessions/{session_id}/end", headers=headers)
    assert ended.status_code == 200

    profile = await client.get("/users/me/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["sessions_completed"] == 1


async def test_open_session_history_is_available_to_mentor_context(client: AsyncClient) -> None:
    headers, session_id = await _workspace(client, "profile-live-history@example.com")
    user = await client.get("/users/me", headers=headers)
    user_id = UUID(user.json()["id"])
    parsed_session_id = UUID(session_id)

    async with db_session.AsyncSessionLocal() as session:
        session.add(
            ExecutionRun(
                session_id=parsed_session_id,
                code_snapshot="print(value)",
                language="python",
                version="3.10.0",
                stderr="NameError: value is not defined",
                exit_code=1,
                status="failed",
                static_analysis_result={"diagnostics": []},
            )
        )
        session.add(
            HintEvent(
                user_id=user_id,
                session_id=parsed_session_id,
                level=1,
                prompt="Give me a hint",
                response="Look at the variable name.",
            )
        )
        await session.commit()

        context = await PersonalizationService(session).get_context(user_id)

    assert context.execution_runs == 1
    assert context.hints_used == 1
    assert context.teaching_style == "scaffolded"
    assert context.rolling_failed_run_ratio == 1.0
    assert any("failed python execution" in item for item in context.recent_activity)
    assert any("level 1 hint" in item for item in context.recent_activity)
    assert (
        "History totals: 0 completed sessions, 1 execution runs, 1 hints"
        in context.prompt_block()
    )


async def test_profile_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/users/me/profile")
    assert response.status_code == 401
