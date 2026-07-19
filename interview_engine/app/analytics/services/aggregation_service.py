from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Optional

from ..models.analytics_event import AnalyticsEvent


class AggregationService:
    def aggregate(self, events: list[AnalyticsEvent]) -> dict[str, Any]:
        event_counts = Counter(event.event_type for event in events)
        language_distribution = Counter(
            str(event.metadata.get("language"))
            for event in events
            if event.metadata.get("language")
        )
        scores = [float(event.metadata["score"]) for event in events if self._score(event) is not None]
        durations = [float(event.metadata["duration_seconds"]) for event in events if self._duration(event) is not None]
        scores_by_date: dict[str, list[float]] = defaultdict(list)
        activity_by_date: Counter[str] = Counter()
        for event in events:
            date = event.timestamp.date().isoformat()
            activity_by_date[date] += 1
            score = self._score(event)
            if score is not None:
                scores_by_date[date].append(score)
        return {
            "total_events": len(events),
            "total_interviews": event_counts["INTERVIEW_STARTED"],
            "completed_interviews": event_counts["INTERVIEW_COMPLETED"],
            "total_questions_answered": event_counts["QUESTION_ANSWERED"],
            "total_traces": event_counts["TRACE_CREATED"],
            "completed_traces": event_counts["TRACE_COMPLETED"],
            "total_problems_solved": event_counts["PROBLEM_SOLVED"],
            "total_hints": event_counts["HINT_REQUESTED"],
            "average_interview_score": round(sum(scores) / len(scores), 2) if scores else None,
            "average_execution_time_seconds": round(sum(durations) / len(durations), 2) if durations else None,
            "event_counts": dict(event_counts),
            "language_distribution": dict(language_distribution),
            "scores_by_date": [
                {"date": date, "score": round(sum(values) / len(values), 2)}
                for date, values in sorted(scores_by_date.items())
            ],
            "activity_by_date": [
                {"date": date, "count": count}
                for date, count in sorted(activity_by_date.items())
            ],
            "recent_activity": [self.event_summary(event) for event in sorted(events, key=lambda item: item.timestamp, reverse=True)[:10]],
        }

    @staticmethod
    def _score(event: AnalyticsEvent) -> Optional[float]:
        value = event.metadata.get("score")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _duration(event: AnalyticsEvent) -> Optional[float]:
        value = event.metadata.get("duration_seconds")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def event_summary(event: AnalyticsEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "metadata": event.metadata,
        }
