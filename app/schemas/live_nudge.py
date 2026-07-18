from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class LiveNudgeRequest(BaseModel):
    session_id: UUID
    problem_id: UUID | None = None
    code: str = Field(default="", max_length=200_000)
    language: str = Field(min_length=1, max_length=64)
    client_detected_signal: str | None = Field(default=None, max_length=128)


class NudgeType(StrEnum):
    orientation = "orientation"
    encourage = "encourage"
    scaffold = "scaffold"
    pinpoint = "pinpoint"
    celebrate = "celebrate"


class LiveNudgeResponse(BaseModel):
    nudge: str = Field(max_length=2_000)
    nudge_type: NudgeType
    stage: str = Field(max_length=128)
    should_display: bool


class LiveNudgeFeedback(BaseModel):
    session_id: UUID
    helpful: bool
