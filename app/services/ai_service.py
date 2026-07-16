"""Provider-neutral LLM boundary; mentor features are delivered in Phase 6."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import LLMProvider, Settings
from app.core.exceptions import AIProviderError


@dataclass(frozen=True)
class LLMConnection:
    provider: LLMProvider
    model: str
    base_url: str | None
    api_key: str | None


class AIService:
    """Resolves provider settings without leaking provider details into routers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def connection(self) -> LLMConnection:
        match self.settings.llm_provider:
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
