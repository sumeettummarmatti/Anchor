from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LearnerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    hint_depth_ceiling: int = Field(ge=1, le=5)
    teaching_style: str
    difficulty_adjustment: float
    intervention_frequency: float = Field(ge=0, le=1)
    rolling_hint_rate: float = Field(ge=0)
    rolling_failed_run_ratio: float = Field(ge=0, le=1)
    rolling_avg_solve_time_seconds: float = Field(ge=0)
    sessions_completed: int = Field(ge=0)
    execution_runs: int = Field(ge=0)
    hints_used: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime
