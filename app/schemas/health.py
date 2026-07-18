from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    environment: str


class LLMHealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    provider: str | None = None
    model: str | None = None
    detail: str | None = None
