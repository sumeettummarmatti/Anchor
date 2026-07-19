from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    project_id: UUID


class EditorEvent(BaseModel):
    current_code: str = Field(max_length=200_000)
    cursor_position: int | None = Field(default=None, ge=0)
    current_function: str | None = Field(default=None, max_length=255)
    open_file: str | None = Field(default=None, max_length=1024)
    typing_pause_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    file_switches: int = Field(default=0, ge=0, le=1000)


class EventBatch(BaseModel):
    events: list[EditorEvent] = Field(min_length=1, max_length=50)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    started_at: datetime
    ended_at: datetime | None
    event_count: int


class StuckScoreResponse(BaseModel):
    score: float
    is_stuck: bool
    signals: dict[str, float]
