from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AnalyticsEvent:
    """Immutable event stored by the append-only analytics repository."""

    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    event_type: str = ""
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
