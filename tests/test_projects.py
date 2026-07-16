from httpx import AsyncClient


async def token_for(client: AsyncClient, email: str) -> dict[str, str]:
    password = "phase-three-password"
    register = await client.post("/auth/register", json={"email": email, "password": password})
    assert register.status_code == 201
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.json()


async def test_project_file_and_session_flow(client: AsyncClient) -> None:
    tokens = await token_for(client, "projects@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    project = await client.post(
        "/projects", headers=headers, json={"name": "Loops", "language": "python"}
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    file = await client.post(
        f"/projects/{project_id}/files",
        headers=headers,
        json={"path": "main.py", "content": "print('hi')"},
    )
    assert file.status_code == 201
    assert (await client.get(f"/projects/{project_id}/files", headers=headers)).json()[0][
        "path"
    ] == "main.py"

    session = await client.post("/sessions", headers=headers, json={"project_id": project_id})
    assert session.status_code == 201
    session_id = session.json()["id"]
    events = await client.post(
        f"/sessions/{session_id}/events",
        headers=headers,
        json={
            "events": [
                {"current_code": "print('hi')", "cursor_position": 11, "open_file": "main.py"}
            ]
        },
    )
    assert events.status_code == 200
    assert events.json()["event_count"] == 1
    assert (await client.post(f"/sessions/{session_id}/end", headers=headers)).json()[
        "ended_at"
    ] is not None


async def test_project_routes_require_authentication_and_ownership(client: AsyncClient) -> None:
    assert (
        await client.post("/projects", json={"name": "Nope", "language": "python"})
    ).status_code == 401
    owner = await token_for(client, "owner@example.com")
    other = await token_for(client, "other@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    project = await client.post(
        "/projects", headers=owner_headers, json={"name": "Private", "language": "python"}
    )
    assert (
        await client.get("/projects/{}".format(project.json()["id"]), headers=other_headers)
    ).status_code == 404
