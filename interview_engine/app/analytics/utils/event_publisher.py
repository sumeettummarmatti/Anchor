from datetime import datetime
from typing import Any, Optional

from ..models.analytics_event import AnalyticsEvent
from ..services.event_processor import EventProcessor


class EventPublisher:
    """Synchronous publishing boundary that can later be replaced by a queue."""

    def __init__(self, processor: EventProcessor):
        self.processor = processor

    def publish(
        self,
        *,
        event_type: str,
        source: str,
        user_id: str,
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AnalyticsEvent:
        return self.processor.process(
            event_type=event_type,
            source=source,
            user_id=user_id,
            metadata=metadata,
            timestamp=timestamp,
        )


class NullEventPublisher:
    """Compatibility default for services constructed without analytics wiring."""

    def publish(self, **kwargs) -> None:
        return None
