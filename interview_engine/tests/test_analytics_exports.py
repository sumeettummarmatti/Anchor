from datetime import datetime, timezone

from interview_engine.app.analytics.repositories.analytics_repository import InMemoryAnalyticsRepository
from interview_engine.app.analytics.services.analytics_service import AnalyticsService
from interview_engine.app.analytics.services.event_processor import EventProcessor
from interview_engine.app.analytics.services.export_service import ExportService


def test_analytics_recommendations_history_and_exports():
    repository = InMemoryAnalyticsRepository()
    processor = EventProcessor(repository)
    timestamp = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)
    for event_type, metadata in [
        ("INTERVIEW_STARTED", {"language": "python", "topic": "graphs"}),
        ("QUESTION_ANSWERED", {"language": "python", "topic": "graphs", "score": 5}),
        ("HINT_REQUESTED", {"language": "python", "topic": "graphs"}),
        ("TRACE_CREATED", {"language": "python", "topic": "graphs"}),
        ("EXECUTION_COMPLETED", {"language": "python", "duration_seconds": 1.2}),
    ]:
        processor.process(
            event_type=event_type,
            source="test",
            user_id="learner-1",
            metadata=metadata,
            timestamp=timestamp,
        )

    service = AnalyticsService(repository)
    overview = service.overview("learner-1")
    assert overview["totals"]["total_events"] == 5
    assert overview["recommendations"]
    assert len(service.history("learner-1", "INTERVIEW_")) == 1

    export = ExportService(service)
    assert '"events"' in export.json_bytes("learner-1").decode("utf-8")
    csv_lines = export.csv_bytes("learner-1").decode("utf-8").splitlines()
    assert csv_lines[0] == "id,user_id,event_type,source,timestamp,metadata"
    assert len(csv_lines) == 6
