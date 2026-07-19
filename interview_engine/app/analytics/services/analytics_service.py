from typing import Any

from ..repositories.analytics_repository import AnalyticsRepository
from .aggregation_service import AggregationService
from .progress_service import ProgressService
from .recommendation_service import RecommendationService
from .snapshot_service import SnapshotService


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository, aggregation=None, snapshot=None, progress=None, recommendations=None):
        self.repository = repository
        self.aggregation = aggregation or AggregationService()
        self.snapshot = snapshot or SnapshotService()
        self.progress = progress or ProgressService()
        self.recommendations = recommendations or RecommendationService()

    def overview(self, user_id: str) -> dict[str, Any]:
        events = self.repository.list_for_user(user_id)
        aggregate = self.aggregation.aggregate(events)
        snapshot = self.snapshot.build(events, aggregate)
        progress = self.progress.build(events, aggregate)
        return {
            "user_id": user_id,
            "totals": {key: value for key, value in aggregate.items() if key not in {"event_counts", "language_distribution", "scores_by_date", "activity_by_date", "recent_activity"}},
            "snapshot": snapshot.__dict__,
            "event_counts": aggregate["event_counts"],
            "language_distribution": aggregate["language_distribution"],
            "scores_by_date": aggregate["scores_by_date"],
            "activity_by_date": aggregate["activity_by_date"],
            "recent_activity": aggregate["recent_activity"],
            "progress": progress,
            "recommendations": self.recommendations.build(events, aggregate, progress),
        }

    def period(self, user_id: str, days: int) -> dict[str, Any]:
        events = self.repository.list_for_user(user_id)
        aggregate = self.aggregation.aggregate(events)
        points = aggregate["activity_by_date"]
        return {"period_days": days, "activity": points[-days:], "progress": self.progress.build(events, aggregate)}

    def history(self, user_id: str, prefix: str) -> list[dict[str, Any]]:
        events = self.repository.list_for_user(user_id)
        return [self.aggregation.event_summary(event) for event in events if event.event_type.startswith(prefix)]
