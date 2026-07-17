from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.static_analysis import Diagnostic


class MentorChatRequest(BaseModel):
    session_id: UUID | None = None
    execution_id: UUID | None = None
    language: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=200_000)
    message: str = Field(min_length=1, max_length=4000)
    diagnostics: list[Diagnostic] = Field(default_factory=list, max_length=100)


class MentorHintRequest(BaseModel):
    session_id: UUID
    language: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=200_000)
    request: str = Field(default="Please give me the next hint.", min_length=1, max_length=4000)
    level: int | None = Field(default=None, ge=1, le=5)
    diagnostics: list[Diagnostic] = Field(default_factory=list, max_length=100)


class ExplainErrorRequest(BaseModel):
    session_id: UUID | None = None
    language: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=200_000)
    error: str = Field(min_length=1, max_length=12_000)
    diagnostics: list[Diagnostic] = Field(default_factory=list, max_length=100)


class MentorResponse(BaseModel):
    message: str
    model: str


class HintResponse(MentorResponse):
    hint_id: UUID
    level: int
    created_at: datetime
