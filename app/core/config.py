from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    GROQ = "groq"
    HUGGINGFACE = "huggingface"
    LMSTUDIO = "lmstudio"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Coding Mentor API"
    environment: str = "development"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    app_secret_key: str = "unsafe-development-secret-change-me"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)
    database_url: str = "postgresql+asyncpg://mentor:mentor@127.0.0.1:5433/mentor"
    redis_url: str = "redis://localhost:6379/0"
    piston_base_url: str = "http://localhost:2000"
    piston_request_timeout_seconds: float = Field(default=15, gt=0, le=60)
    static_analysis_timeout_seconds: float = Field(default=5, gt=0, le=30)
    llm_request_timeout_seconds: float = Field(default=30, gt=0, le=120)
    recommendation_artifact_dir: str = "artifacts/recommender"

    llm_provider: LLMProvider = LLMProvider.OLLAMA
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model: str = "qwen3:8b"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    hf_api_key: str | None = None
    hf_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_api_key: str = "lm-studio"
    lmstudio_model: str = "local-model"

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str | None = None

    @property
    def jwt_algorithm(self) -> str:
        """HS256: HMAC with SHA-256, used for locally issued JWTs."""
        return "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
