from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("INTERVIEW_DATABASE_URL", "sqlite:///./interviews.db")
    ai_provider: str = os.getenv("INTERVIEW_AI_PROVIDER", "mock")
    max_questions: int = int(os.getenv("INTERVIEW_MAX_QUESTIONS", "5"))
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key: str = os.getenv("INTERVIEW_API_KEY", "dev-api-key")
    repository: str = os.getenv("INTERVIEW_REPOSITORY", "memory")
    sqlite_path: str = os.getenv("INTERVIEW_SQLITE_PATH", "./interviews.sqlite3")

settings = Settings()
