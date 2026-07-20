"""Provider-neutral LLM boundary used only with audited prompt contexts."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import structlog
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import LLMProvider, Settings
from app.core.exceptions import AIProviderError, ConfigurationError
from app.schemas.static_analysis import Diagnostic
from app.services.personalization_service import AdaptationContext

if TYPE_CHECKING:
    from app.schemas.live_nudge import LiveNudgeRequest, LiveNudgeResponse

logger = structlog.get_logger(__name__)


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

    def __init__(
        self,
        settings: Settings,
        client: AsyncOpenAI | None = None,
        groq_api_key: str | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self.groq_api_key = groq_api_key

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
                    self.groq_api_key or self.settings.groq_api_key,
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
        if self.groq_api_key:
            return (LLMProvider.GROQ,)
        configured = self.settings.llm_provider
        if configured is LLMProvider.AUTO:
            return (LLMProvider.OLLAMA, LLMProvider.LMSTUDIO)
        if configured is LLMProvider.OLLAMA:
            return (LLMProvider.OLLAMA, LLMProvider.LMSTUDIO)
        return (configured,)

    async def probe(
        self, timeout_seconds: float = 3.0
    ) -> tuple[bool, str | None, str | None, str | None]:
        """Check provider/model readiness without sending a completion request."""
        failures: list[str] = []
        for provider in self.provider_order():
            connection = self.connection(provider)
            if not connection.api_key:
                failures.append(f"{provider.value}: not configured")
                continue
            client = AsyncOpenAI(
                api_key=connection.api_key,
                base_url=connection.base_url,
                timeout=httpx.Timeout(timeout_seconds, connect=1.5),
                max_retries=0,
            )
            try:
                model = await self._resolve_model(connection, client)
                return True, provider.value, model, None
            except Exception:
                failures.append(f"{provider.value}: unavailable")
            finally:
                await client.close()
        return False, None, None, "; ".join(failures) or "No LLM provider is configured."

    def _client_for(self, connection: LLMConnection, provider: LLMProvider) -> AsyncOpenAI:
        if self._client is not None and not self.groq_api_key and provider is self.settings.llm_provider:
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
        from app.prompt_templates import explain_error, live_nudge, mentor_chat, mentor_hint

        builders = {
            "chat": mentor_chat.build,
            "hint": mentor_hint.build,
            "explain_error": explain_error.build,
            "live_nudge": live_nudge.build,
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
                if context.intent == "live_nudge":
                    request["temperature"] = 0.2
                    request["max_tokens"] = 96
                if provider is LLMProvider.OLLAMA:
                    # Qwen's reasoning mode can be very slow locally. Keep it
                    # disabled by default and cap generated tokens.
                    request["extra_body"] = {
                        "think": self.settings.ollama_think,
                        "options": {
                            "num_predict": (
                                min(self.settings.ollama_num_predict, 128)
                                if context.intent == "live_nudge"
                                else self.settings.ollama_num_predict
                            )
                        },
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

    async def live_nudge(
        self,
        request: LiveNudgeRequest,
        adaptation: AdaptationContext,
        *,
        session: AsyncSession,
        user_id: UUID,
    ) -> LiveNudgeResponse:
        """Generate, suppress, and persist one short Live Tutor nudge."""
        from app.core.live_nudge_state import (
            check_rate_limit,
            record_nudge,
            should_suppress_posttrigger,
            should_suppress_pretrigger,
        )
        from app.models.hint_event import HintEvent
        from app.repositories.hint_repository import HintRepository
        from app.schemas.live_nudge import LiveNudgeResponse, NudgeType

        await check_rate_limit(user_id, request.session_id)
        if await should_suppress_pretrigger(request.session_id):
            return LiveNudgeResponse(
                nudge="", nudge_type=NudgeType.encourage, stage="", should_display=False
            )

        context = PromptContext(
            intent="live_nudge",
            language=request.language,
            code=request.code,
            learner_message=request.client_detected_signal or "idle pause",
            adaptation=adaptation,
        )
        raw_text, _model = await self.complete(context)
        try:
            parsed = self._parse_live_nudge_json(raw_text)
            nudge = str(parsed.get("nudge", "")).strip()
            nudge_type = NudgeType(parsed.get("nudge_type", NudgeType.encourage))
            stage = str(parsed.get("stage", "unknown")).strip() or "unknown"
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "live_nudge_json_parse_failed",
                user_id=str(user_id),
                session_id=str(request.session_id),
            )
            # Reasoning models sometimes return a useful plain-text nudge
            # instead of the requested JSON envelope. Keep that guidance
            # visible rather than silently dropping the response.
            import re

            fallback = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            fallback = fallback.split(".", 1)[0].strip()[:2_000]
            if fallback:
                return LiveNudgeResponse(
                    nudge=fallback,
                    nudge_type=NudgeType.encourage,
                    stage="exploring",
                    should_display=True,
                )
            return LiveNudgeResponse(
                nudge="", nudge_type=NudgeType.encourage, stage="unknown", should_display=False
            )

        if not nudge or await should_suppress_posttrigger(request.session_id, stage):
            return LiveNudgeResponse(
                nudge="", nudge_type=nudge_type, stage=stage, should_display=False
            )

        await record_nudge(request.session_id, stage)
        await HintRepository(session).create(
            HintEvent(
                user_id=user_id,
                session_id=request.session_id,
                level=0,
                prompt=request.code[:500],
                response=nudge,
                source="nudge",
            )
        )
        return LiveNudgeResponse(
            nudge=nudge, nudge_type=nudge_type, stage=stage, should_display=True
        )

    @staticmethod
    def _parse_live_nudge_json(raw_text: str) -> dict[str, object]:
        """Accept strict JSON plus the markdown fences local models often add."""
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].lstrip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise TypeError("Live nudge JSON must be an object.")
        return parsed
