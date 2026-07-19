from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventIngestRequest(BaseModel):
    event_type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None


class AnalyticsEventResponse(BaseModel):
    id: str
    user_id: str
    event_type: str
    source: str
    timestamp: datetime
    metadata: dict[str, Any]
