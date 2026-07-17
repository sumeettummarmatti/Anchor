"""Provider-neutral LLM boundary used only with audited prompt contexts."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAIError

from app.core.config import LLMProvider, Settings
from app.core.exceptions import AIProviderError, ConfigurationError
from app.schemas.static_analysis import Diagnostic


@dataclass(frozen=True)
class LLMConnection:
    provider: LLMProvider
    model: str
    base_url: str | None
    api_key: str | None


@dataclass(frozen=True)
class PromptContext:
    intent: str
    language: str
    code: str
    learner_message: str
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    runtime_error: str | None = None
    hint_level: int | None = None

    def as_prompt(self) -> str:
        diagnostics = (
            "\n".join(
                f"- {item.code} at {item.line}:{item.column}: {item.message}"
                for item in self.diagnostics
            )
            or "None"
        )
        parts = [
            f"Task: {self.intent}",
            f"Language: {self.language}",
            f"Learner message: {self.learner_message}",
            f"Diagnostics:\n{diagnostics}",
            f"Code:\n```{self.language}\n{self.code}\n```",
        ]
        if self.runtime_error:
            parts.insert(4, f"Runtime or compiler error:\n{self.runtime_error}")
        if self.hint_level is not None:
            parts.insert(1, f"Hint level: {self.hint_level} of 5")
        return "\n\n".join(parts)


class AIService:
    """Executes a template-built prompt through an OpenAI-compatible provider."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        self._client = client

    def connection(self) -> LLMConnection:
        match self.settings.llm_provider:
            case LLMProvider.OLLAMA:
                return LLMConnection(
                    LLMProvider.OLLAMA,
                    self.settings.ollama_model,
                    self.settings.ollama_base_url,
                    self.settings.ollama_api_key,
                )
            case LLMProvider.OPENAI:
                return LLMConnection(
                    LLMProvider.OPENAI,
                    self.settings.openai_model,
                    None,
                    self.settings.openai_api_key,
                )
            case LLMProvider.GROQ:
                return LLMConnection(
                    LLMProvider.GROQ,
                    self.settings.groq_model,
                    "https://api.groq.com/openai/v1",
                    self.settings.groq_api_key,
                )
            case LLMProvider.HUGGINGFACE:
                return LLMConnection(
                    LLMProvider.HUGGINGFACE,
                    self.settings.hf_model,
                    "https://router.huggingface.co/v1",
                    self.settings.hf_api_key,
                )
            case LLMProvider.LMSTUDIO:
                return LLMConnection(
                    LLMProvider.LMSTUDIO,
                    self.settings.lmstudio_model,
                    self.settings.lmstudio_base_url,
                    self.settings.lmstudio_api_key,
                )
        raise AIProviderError("Unsupported LLM provider.")

    async def complete(self, context: PromptContext) -> tuple[str, str]:
        """Generate a response. Callers may supply context, never raw prompt strings."""
        from app.prompt_templates import explain_error, mentor_chat, mentor_hint

        builders = {
            "chat": mentor_chat.build,
            "hint": mentor_hint.build,
            "explain_error": explain_error.build,
        }
        try:
            builder = builders[context.intent]
        except KeyError as exc:
            raise AIProviderError("Unsupported mentor request.") from exc
        connection = self.connection()
        if not connection.api_key:
            raise ConfigurationError(f"{connection.provider.value} is not configured.")
        client = self._client or AsyncOpenAI(
            api_key=connection.api_key,
            base_url=connection.base_url,
            timeout=httpx.Timeout(self.settings.llm_request_timeout_seconds),
            max_retries=2,
        )
        system, user = builder(context)
        try:
            completion = await client.chat.completions.create(
                model=connection.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
        except (APITimeoutError, APIConnectionError) as exc:
            raise AIProviderError("The AI provider timed out or could not be reached.") from exc
        except OpenAIError as exc:
            raise AIProviderError() from exc
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise AIProviderError("The AI provider returned an empty response.")
        return content, connection.model
