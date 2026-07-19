import csv
import io
import json
from typing import Any

from .analytics_service import AnalyticsService
from .aggregation_service import AggregationService


class ExportService:
    def __init__(self, analytics_service: AnalyticsService):
        self.analytics_service = analytics_service

    def payload(self, user_id: str) -> dict[str, Any]:
        events = self.analytics_service.repository.list_for_user(user_id)
        overview = self.analytics_service.overview(user_id)
        return {
            "user_id": user_id,
            "overview": overview,
            "events": [AggregationService.event_summary(event) for event in events],
        }

    def json_bytes(self, user_id: str) -> bytes:
        return json.dumps(self.payload(user_id), indent=2).encode("utf-8")

    def csv_bytes(self, user_id: str) -> bytes:
        events = self.analytics_service.repository.list_for_user(user_id)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "user_id", "event_type", "source", "timestamp", "metadata"])
        writer.writeheader()
        for event in events:
            writer.writerow({
                "id": event.id,
                "user_id": event.user_id,
                "event_type": event.event_type,
                "source": event.source,
                "timestamp": event.timestamp.isoformat(),
                "metadata": json.dumps(event.metadata, sort_keys=True),
            })
        return output.getvalue().encode("utf-8")
