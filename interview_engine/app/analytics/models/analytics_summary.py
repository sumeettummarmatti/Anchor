from dataclasses import dataclass
from typing import Any

from .learning_snapshot import LearningSnapshot


@dataclass
class AnalyticsSummary:
    totals: dict[str, Any]
    snapshot: LearningSnapshot
    event_counts: dict[str, int]
    language_distribution: dict[str, int]
    scores_by_date: list[dict[str, Any]]
    activity_by_date: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
