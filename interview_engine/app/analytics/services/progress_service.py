from datetime import datetime, timedelta, timezone
from typing import Any

from ..models.analytics_event import AnalyticsEvent


class ProgressService:
    def build(self, events: list[AnalyticsEvent], aggregate: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        recent = [event for event in events if event.timestamp >= now - timedelta(days=7)]
        active_days = len({event.timestamp.date().isoformat() for event in events if event.timestamp >= now - timedelta(days=30)})
        scores = aggregate.get("scores_by_date", [])
        change = None
        if len(scores) >= 2:
            change = round(scores[-1]["score"] - scores[0]["score"], 2)
        return {
            "learning_velocity_7d": round(len(recent) / 7, 2),
            "active_days_30d": active_days,
            "score_change": change,
            "score_trend": scores,
            "weekly_growth": self._period_count(events, 7),
            "monthly_growth": self._period_count(events, 30),
        }

    @staticmethod
    def _period_count(events: list[AnalyticsEvent], days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return sum(event.timestamp >= cutoff for event in events)
