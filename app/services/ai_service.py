"""Provider-neutral LLM boundary used only with audited prompt contexts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAIError

from app.core.config import LLMProvider, Settings
from app.core.exceptions import AIProviderError, ConfigurationError
from app.schemas.static_analysis import Diagnostic
from app.services.personalization_service import AdaptationContext


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
    adaptation: AdaptationContext | None = None

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
        if self.adaptation is not None:
            parts.insert(
                1,
                "Learner adaptation: "
                f"teaching style={self.adaptation.teaching_style}, "
                f"hint ceiling={self.adaptation.hint_depth_ceiling}, "
                f"difficulty adjustment={self.adaptation.difficulty_adjustment:+.2f}, "
                f"intervention frequency={self.adaptation.intervention_frequency:.2f}.",
            )
        return "\n\n".join(parts)


class AIService:
    """Executes a template-built prompt through an OpenAI-compatible provider."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        self._client = client

    def connection(self, provider: LLMProvider | None = None) -> LLMConnection:
        provider = provider or self.settings.llm_provider
        match provider:
            case LLMProvider.AUTO:
                raise AIProviderError(
                    "The automatic provider selector is not a concrete connection."
                )
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

    def provider_order(self) -> tuple[LLMProvider, ...]:
        """Return providers to try, with local fallback for Ollama/auto."""
        configured = self.settings.llm_provider
        if configured is LLMProvider.AUTO:
            return (LLMProvider.OLLAMA, LLMProvider.LMSTUDIO)
        if configured is LLMProvider.OLLAMA:
            return (LLMProvider.OLLAMA, LLMProvider.LMSTUDIO)
        return (configured,)

    def _client_for(self, connection: LLMConnection, provider: LLMProvider) -> AsyncOpenAI:
        if self._client is not None and provider is self.settings.llm_provider:
            return self._client
        return AsyncOpenAI(
            api_key=connection.api_key or "local",
            base_url=connection.base_url,
            timeout=httpx.Timeout(self.settings.llm_request_timeout_seconds, connect=5.0),
            # The service owns fallback/retry behavior. The SDK must not repeat
            # a slow local request behind our back.
            max_retries=0,
        )

    async def _resolve_model(self, connection: LLMConnection, client: AsyncOpenAI) -> str:
        """Resolve a local model dynamically when its configured name is blank."""
        if connection.model and connection.model != "local-model":
            return connection.model
        try:
            models = await client.models.list()
        except (APITimeoutError, APIConnectionError, OpenAIError) as exc:
            raise AIProviderError(
                f"Could not discover a loaded {connection.provider.value} model."
            ) from exc
        ids: Iterable[str] = (item.id for item in models.data if getattr(item, "id", None))
        model = next(iter(ids), None)
        if not model:
            raise AIProviderError(f"No loaded model was found in {connection.provider.value}.")
        return model

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
        system, user = builder(context)
        failures: list[str] = []
        for provider in self.provider_order():
            connection = self.connection(provider)
            if not connection.api_key:
                if len(self.provider_order()) == 1:
                    raise ConfigurationError(f"{connection.provider.value} is not configured.")
                failures.append(f"{provider.value}: not configured")
                continue
            client = self._client_for(connection, provider)
            try:
                model = await self._resolve_model(connection, client)
                request = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                if provider is LLMProvider.OLLAMA:
                    # Qwen's reasoning mode can be very slow locally. Keep it
                    # disabled by default and cap generated tokens.
                    request["extra_body"] = {
                        "think": self.settings.ollama_think,
                        "options": {"num_predict": self.settings.ollama_num_predict},
                    }
                completion = await client.chat.completions.create(**request)
                content = completion.choices[0].message.content if completion.choices else None
                if not content:
                    raise AIProviderError("The AI provider returned an empty response.")
                return content, model
            except (APITimeoutError, APIConnectionError):
                failures.append(f"{provider.value}: timed out or unreachable")
                continue
            except OpenAIError:
                failures.append(f"{provider.value}: request failed")
                continue
            except AIProviderError as exc:
                failures.append(f"{provider.value}: {exc.detail}")
                continue

        detail = "AI providers unavailable. " + "; ".join(failures)
        raise AIProviderError(detail)
