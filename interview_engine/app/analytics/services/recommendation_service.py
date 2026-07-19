from typing import Any

from ..models.analytics_event import AnalyticsEvent


class RecommendationService:
    """Small deterministic recommendation layer ready for a model-backed replacement."""

    def build(self, events: list[AnalyticsEvent], aggregate: dict[str, Any], progress: dict[str, Any]) -> list[str]:
        if not events:
            return ["Run a trace or complete an interview to start building your learning profile."]
        recommendations: list[str] = []
        average = aggregate.get("average_interview_score")
        if average is not None and average < 7:
            recommendations.append("Review the fundamentals behind your recent interview answers before attempting another hard problem.")
        elif progress.get("score_change") is not None and progress["score_change"] > 0:
            recommendations.append(f"Interview scores have improved by {progress['score_change']} points across your recorded trend.")
        if aggregate.get("total_hints", 0) > 0:
            recommendations.append("Try one independent attempt before requesting a hint to strengthen recall.")
        if aggregate.get("total_traces", 0) > aggregate.get("completed_interviews", 0):
            recommendations.append("Pair your execution traces with interview explanations to practice communicating your reasoning.")
        topics = [
            str(event.metadata.get("topic"))
            for event in events
            if event.metadata.get("topic")
        ]
        if topics:
            recommendations.append(f"Keep revisiting {max(set(topics), key=topics.count)} problems to reinforce your most frequent topic.")
        return recommendations or ["Keep practicing consistently and review your latest activity after each session."]
