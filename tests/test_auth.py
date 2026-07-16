from httpx import AsyncClient


async def register(client: AsyncClient, email: str = "learner@example.com") -> dict[str, object]:
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": "safe-password-123", "display_name": "Learner"},
    )
    assert response.status_code == 201
    return response.json()


async def login(client: AsyncClient, email: str = "learner@example.com") -> dict[str, str]:
    response = await client.post(
        "/auth/login", json={"email": email, "password": "safe-password-123"}
    )
    assert response.status_code == 200
    return response.json()


async def test_register_and_reject_duplicate_email(client: AsyncClient) -> None:
    user = await register(client)
    assert user["email"] == "learner@example.com"
    assert user["role"] == "student"

    duplicate = await client.post(
        "/auth/register", json={"email": "learner@example.com", "password": "safe-password-123"}
    )
    assert duplicate.status_code == 409


async def test_login_returns_tokens_and_rejects_invalid_credentials(client: AsyncClient) -> None:
    await register(client)
    failure = await client.post(
        "/auth/login", json={"email": "learner@example.com", "password": "incorrect-password"}
    )
    assert failure.status_code == 401

    tokens = await login(client)
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]


async def test_refresh_rotation_and_logout_revoke_tokens(client: AsyncClient) -> None:
    await register(client)
    tokens = await login(client)
    refreshed = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reused = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401

    logout = await client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 204
    revoked = await client.post(
        "/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert revoked.status_code == 401


async def test_current_user_requires_authentication_and_can_be_updated(client: AsyncClient) -> None:
    unauthenticated = await client.get("/users/me")
    assert unauthenticated.status_code == 401

    await register(client)
    tokens = await login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = await client.get("/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Learner"

    invalid_update = await client.patch("/users/me", headers=headers, json={"display_name": ""})
    assert invalid_update.status_code == 422
    update = await client.patch("/users/me", headers=headers, json={"display_name": "Ada"})
    assert update.status_code == 200
    assert update.json()["display_name"] == "Ada"


async def test_oauth_reports_missing_configuration_and_unknown_provider(
    client: AsyncClient,
) -> None:
    google = await client.get("/auth/oauth/google/login", follow_redirects=False)
    unknown = await client.get("/auth/oauth/other/login", follow_redirects=False)
    callback = await client.get("/auth/oauth/github/callback", follow_redirects=False)
    assert google.status_code == 503
    assert unknown.status_code == 503
    assert callback.status_code == 503
