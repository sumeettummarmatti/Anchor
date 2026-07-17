"""Single source of truth for recommendation training and serving features."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.ml.data.synthetic_problems import LANGUAGES, TOPICS, SyntheticProblem

USER_FEATURE_NAMES = (
    "hint_ceiling",
    "difficulty_adjustment",
    "hint_rate",
    "failed_run_ratio",
    "average_solve_time",
    "style_socratic",
    "style_encouraging",
    "style_scaffolded",
    "effective_skill",
    *tuple(f"topic_{topic}" for topic in TOPICS),
    *tuple(f"language_{language}" for language in LANGUAGES),
)
PROBLEM_FEATURE_NAMES = (
    *tuple(f"topic_{topic}" for topic in TOPICS),
    "difficulty",
    *tuple(f"language_{language}" for language in LANGUAGES),
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def effective_skill(profile: Mapping[str, Any]) -> float:
    """Estimate a 1-5 productive-struggle difficulty from profile aggregates."""
    adjustment = _number(profile.get("difficulty_adjustment"))
    failed_ratio = _clamp(_number(profile.get("rolling_failed_run_ratio")), 0.0, 1.0)
    hint_rate = _clamp(_number(profile.get("rolling_hint_rate")) / 2.0, 0.0, 1.0)
    return _clamp(3.0 + adjustment * 1.5 - failed_ratio * 1.0 - hint_rate * 0.3, 1.0, 5.0)


def _topic_strengths(profile: Mapping[str, Any]) -> list[float]:
    supplied = profile.get("topic_strengths")
    if isinstance(supplied, Mapping):
        return [_clamp(_number(supplied.get(topic), 0.5), 0.0, 1.0) for topic in TOPICS]
    skill = effective_skill(profile)
    baseline = _clamp(0.35 + skill / 10.0, 0.0, 1.0)
    return [baseline for _ in TOPICS]


def _language_preferences(profile: Mapping[str, Any]) -> list[float]:
    supplied = profile.get("language_preferences")
    if isinstance(supplied, Mapping):
        return [_clamp(_number(supplied.get(language), 0.5), 0.0, 1.0) for language in LANGUAGES]
    language = str(profile.get("language", "python")).lower()
    return [1.0 if item == language else 0.35 for item in LANGUAGES]


def user_feature_vector(profile: Mapping[str, Any]) -> list[float]:
    style = str(profile.get("teaching_style", "socratic"))
    style_values = [
        1.0 if style == item else 0.0 for item in ("socratic", "encouraging", "scaffolded")
    ]
    return [
        _clamp(_number(profile.get("hint_depth_ceiling"), 5.0) / 5.0, 0.0, 1.0),
        _clamp((_number(profile.get("difficulty_adjustment")) + 1.0) / 2.0, 0.0, 1.0),
        _clamp(_number(profile.get("rolling_hint_rate")) / 2.0, 0.0, 1.0),
        _clamp(_number(profile.get("rolling_failed_run_ratio")), 0.0, 1.0),
        _clamp(_number(profile.get("rolling_avg_solve_time_seconds")) / 600.0, 0.0, 1.0),
        *style_values,
        effective_skill(profile) / 5.0,
        *_topic_strengths(profile),
        *_language_preferences(profile),
    ]


def problem_feature_vector(problem: SyntheticProblem) -> list[float]:
    tags = set(problem.topic_tags)
    return [
        *[1.0 if topic in tags else 0.0 for topic in TOPICS],
        _clamp(problem.difficulty / 5.0, 0.0, 1.0),
        *[1.0 if language == problem.language else 0.0 for language in LANGUAGES],
    ]
