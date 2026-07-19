from collections import Counter
from typing import Any

from ..models.analytics_event import AnalyticsEvent
from ..models.learning_snapshot import LearningSnapshot


class SnapshotService:
    def build(self, events: list[AnalyticsEvent], aggregate: dict[str, Any]) -> LearningSnapshot:
        languages = Counter(
            str(event.metadata.get("language"))
            for event in events
            if event.metadata.get("language")
        )
        last_active = max((event.timestamp for event in events), default=None)
        return LearningSnapshot(
            total_problems=aggregate.get("total_problems_solved", 0),
            total_interviews=aggregate.get("completed_interviews", 0),
            average_score=aggregate.get("average_interview_score"),
            favorite_language=languages.most_common(1)[0][0] if languages else None,
            current_streak=0,
            last_active=last_active.isoformat() if last_active else None,
        )
