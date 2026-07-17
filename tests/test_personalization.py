from httpx import AsyncClient

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


async def test_profile_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/users/me/profile")
    assert response.status_code == 401
