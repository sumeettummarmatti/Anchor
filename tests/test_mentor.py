import pytest
from httpx import AsyncClient

from app.core.config import LLMProvider, Settings
from app.core.exceptions import ConfigurationError
from app.services.ai_service import AIService, PromptContext
from tests.test_projects import token_for


async def _session(client: AsyncClient, email: str) -> tuple[dict[str, str], str]:
    tokens = await token_for(client, email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    project = await client.post(
        "/projects", headers=headers, json={"name": "Mentor test", "language": "python"}
    )
    session = await client.post(
        "/sessions", headers=headers, json={"project_id": project.json()["id"]}
    )
    return headers, session.json()["id"]


async def test_ollama_is_the_default_provider() -> None:
    settings = Settings(_env_file=None)
    connection = AIService(settings).connection()
    assert connection.provider is LLMProvider.OLLAMA
    assert connection.model == "qwen3:8b"


async def test_remote_provider_without_a_key_is_rejected() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider=LLMProvider.OPENAI,
        openai_api_key=None,
    )
    context = PromptContext("chat", "python", "print(1)", "Help me understand this.")
    with pytest.raises(ConfigurationError):
        await AIService(settings).complete(context)


async def test_hint_progression_is_persisted_and_cannot_be_skipped(
    client: AsyncClient, monkeypatch
) -> None:
    contexts: list[PromptContext] = []

    async def fake_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        contexts.append(context)
        return f"hint {context.hint_level}", "test-model"

    monkeypatch.setattr(AIService, "complete", fake_complete)
    headers, session_id = await _session(client, "mentor-hints@example.com")
    initial = {
        "session_id": session_id,
        "language": "python",
        "code": "print(1)",
        "request": "Help me understand the next step",
    }
    first = await client.post("/mentor/hint", headers=headers, json=initial)
    assert first.status_code == 200
    assert first.json()["level"] == 1
    assert contexts[0].hint_level == 1

    skipped = await client.post("/mentor/hint", headers=headers, json={**initial, "level": 3})
    assert skipped.status_code == 409

    second = await client.post("/mentor/hint", headers=headers, json=initial)
    assert second.status_code == 200
    assert second.json()["level"] == 2


async def test_chat_and_error_explanation_use_prompt_context(
    client: AsyncClient, monkeypatch
) -> None:
    contexts: list[PromptContext] = []

    async def fake_complete(self: AIService, context: PromptContext) -> tuple[str, str]:
        contexts.append(context)
        return "Try inspecting the traceback.", "test-model"

    monkeypatch.setattr(AIService, "complete", fake_complete)
    tokens = await token_for(client, "mentor-chat@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    chat = await client.post(
        "/mentor/chat",
        headers=headers,
        json={"language": "python", "code": "print(value)", "message": "Why does this fail?"},
    )
    error = await client.post(
        "/mentor/explain-error",
        headers=headers,
        json={
            "language": "python",
            "code": "print(value)",
            "error": "NameError: name 'value' is not defined",
        },
    )
    assert chat.status_code == 200
    assert error.status_code == 200
    assert [context.intent for context in contexts] == ["chat", "explain_error"]
    assert contexts[1].runtime_error is not None
    assert contexts[0].adaptation is not None
    assert "Learner adaptation:" in contexts[0].as_prompt()
    assert chat.json()["personalization"]["teaching_style"] == "socratic"
    assert error.json()["personalization"]["hint_depth_ceiling"] == 5
