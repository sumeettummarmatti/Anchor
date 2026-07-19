import json

import pytest

from interview_engine.app.analytics.models.analytics_event import AnalyticsEvent
from interview_engine.app.analytics.repositories.analytics_repository import InMemoryAnalyticsRepository, SQLiteAnalyticsRepository
from interview_engine.app.analytics.services.event_processor import EventProcessor
from interview_engine.app.analytics.utils.event_publisher import EventPublisher, NullEventPublisher


def test_event_processor_normalizes_and_persists_events():
    repository = InMemoryAnalyticsRepository()
    event = EventProcessor(repository).process(
        event_type=" interview_started ",
        source=" Interview ",
        user_id=" learner-1 ",
        metadata={"difficulty": "Easy"},
    )

    assert isinstance(event, AnalyticsEvent)
    assert event.event_type == "INTERVIEW_STARTED"
    assert event.source == "interview"
    assert event.user_id == "learner-1"
    assert repository.get(event.id) == event


def test_event_processor_rejects_unknown_and_non_json_metadata():
    processor = EventProcessor(InMemoryAnalyticsRepository())
    with pytest.raises(ValueError, match="Unsupported analytics event type"):
        processor.process(event_type="NOT_CONFIGURED", source="test", user_id="u")
    with pytest.raises(ValueError, match="JSON serializable"):
        processor.process(event_type="TRACE_CREATED", source="test", user_id="u", metadata={"bad": object()})


def test_event_types_are_loaded_from_json_configuration(tmp_path):
    event_types_path = tmp_path / "event_types.json"
    event_types_path.write_text(json.dumps({"CUSTOM_ACTIVITY": "A configured activity."}), encoding="utf-8")
    processor = EventProcessor(InMemoryAnalyticsRepository(), event_types_path)

    event = processor.process(event_type="custom_activity", source="mentor", user_id="u")

    assert event.event_type == "CUSTOM_ACTIVITY"


def test_event_publisher_and_null_publisher_share_compatible_interface():
    repository = InMemoryAnalyticsRepository()
    event = EventPublisher(EventProcessor(repository)).publish(
        event_type="TRACE_CREATED", source="visualization", user_id="u", metadata={"trace_id": "t-1"}
    )
    assert repository.get(event.id) == event
    assert NullEventPublisher().publish(event_type="TRACE_CREATED", source="visualization", user_id="u") is None


def test_sqlite_analytics_repository_is_append_only(tmp_path):
    repository = SQLiteAnalyticsRepository(str(tmp_path / "analytics.sqlite3"))
    event = EventProcessor(repository).process(event_type="PROBLEM_SOLVED", source="problems", user_id="u")

    assert repository.get(event.id) == event
    assert repository.list_for_user("u") == [event]
    with pytest.raises(ValueError, match="already exists"):
        repository.save(event)
