import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..models.analytics_event import AnalyticsEvent
from ..repositories.analytics_repository import AnalyticsRepository

logger = logging.getLogger(__name__)
DEFAULT_EVENT_TYPES_PATH = Path(__file__).resolve().parents[1] / "assets" / "event_types.json"


def load_event_types(path: Optional[Path] = None) -> dict[str, str]:
    event_types_path = path or DEFAULT_EVENT_TYPES_PATH
    try:
        payload = json.loads(event_types_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load analytics event types from {event_types_path}") from exc
    if isinstance(payload, dict):
        return {str(name).strip().upper(): str(description) for name, description in payload.items()}
    if isinstance(payload, list):
        return {str(name).strip().upper(): "" for name in payload}
    raise RuntimeError("Analytics event types must be a JSON object or list")


class EventProcessor:
    def __init__(self, repository: AnalyticsRepository, event_types_path: Optional[Path] = None):
        self.repository = repository
        self.event_types_path = event_types_path or DEFAULT_EVENT_TYPES_PATH
        self.event_types = load_event_types(self.event_types_path)

    def process(
        self,
        *,
        event_type: str,
        source: str,
        user_id: str,
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AnalyticsEvent:
        normalized_type = event_type.strip().upper()
        normalized_source = source.strip().lower()
        normalized_user = user_id.strip()
        if normalized_type not in self.event_types:
            raise ValueError(f"Unsupported analytics event type: {normalized_type}")
        if not normalized_source:
            raise ValueError("Event source must not be blank")
        if not normalized_user:
            raise ValueError("Event user_id must not be blank")
        normalized_metadata = dict(metadata or {})
        try:
            json.dumps(normalized_metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError("Event metadata must be JSON serializable") from exc
        event_timestamp = timestamp or datetime.now(timezone.utc)
        if event_timestamp.tzinfo is None:
            event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
        else:
            event_timestamp = event_timestamp.astimezone(timezone.utc)
        event = AnalyticsEvent(
            user_id=normalized_user,
            event_type=normalized_type,
            source=normalized_source,
            timestamp=event_timestamp,
            metadata=normalized_metadata,
        )
        self.repository.save(event)
        logger.info("Analytics event persisted type=%s source=%s user_id=%s", event.event_type, event.source, event.user_id)
        return event
