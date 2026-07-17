from httpx import AsyncClient

from tests.test_projects import token_for


async def test_static_analysis_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/static-analysis/run", json={"language": "python", "code": "print('hello')"}
    )
    assert response.status_code == 401


async def test_python_static_analysis_returns_normalized_diagnostics(
    client: AsyncClient,
) -> None:
    tokens = await token_for(client, "lint@example.com")
    response = await client.post(
        "/static-analysis/run",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"language": "python", "code": "import os\n"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analyzer"] == "ruff"
    assert body["available"] is True
    assert body["diagnostics"][0]["code"] == "F401"
    assert body["diagnostics"][0]["line"] == 1


async def test_unsupported_static_analysis_is_non_blocking(client: AsyncClient) -> None:
    tokens = await token_for(client, "lint-unsupported@example.com")
    response = await client.post(
        "/static-analysis/run",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"language": "rust", "code": "fn main() {}"},
    )
    assert response.status_code == 200
    assert response.json()["available"] is False
