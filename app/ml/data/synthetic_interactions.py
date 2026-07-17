"""SYNTHETIC DATA — replace with real interaction logs once Phase 11 has volume.

Do not let this module's assumptions leak into production feature engineering without review.
The labels are rule-derived rather than random so a small recommendation model can learn a
directional signal during local development.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ml.data.synthetic_problems import (
    LANGUAGES,
    TOPICS,
    SyntheticProblem,
    synthetic_problem_catalog,
)
from app.ml.features import problem_feature_vector, user_feature_vector


@dataclass(frozen=True)
class StubLearner:
    id: str
    archetype: str
    profile: dict[str, object]


@dataclass(frozen=True)
class TrainingPair:
    learner_id: str
    problem: SyntheticProblem
    user_features: tuple[float, ...]
    problem_features: tuple[float, ...]
    label: int


def stub_learners() -> list[StubLearner]:
    """Return 20 deterministic learner profiles for local recommender validation.

    Each profile combines a focus topic, preferred language, teaching style, skill level,
    hint dependence, and failed-run history.  They intentionally represent different
    learners, rather than 20 copies of one archetype, so training and ranking tests can
    prove that the model responds to learner-specific signals.
    """

    specs = (
        ("arrays_novice", "arrays", "python", "scaffolded", -0.85, 1.8, 0.80, 520),
        ("arrays_builder", "arrays", "javascript", "encouraging", -0.25, 1.1, 0.35, 300),
        ("arrays_solver", "arrays", "python", "socratic", 0.65, 0.3, 0.08, 100),
        ("strings_novice", "strings", "java", "scaffolded", -0.70, 1.7, 0.72, 480),
        ("strings_solver", "strings", "python", "socratic", 0.55, 0.25, 0.10, 120),
        ("hashing_builder", "hashing", "javascript", "encouraging", 0.00, 1.0, 0.28, 260),
        ("hashing_solver", "hashing", "python", "socratic", 0.80, 0.15, 0.06, 90),
        ("recursion_novice", "recursion", "java", "scaffolded", -0.90, 1.9, 0.85, 560),
        ("recursion_builder", "recursion", "python", "encouraging", -0.10, 1.25, 0.40, 320),
        ("recursion_solver", "recursion", "javascript", "socratic", 0.50, 0.4, 0.15, 180),
        ("sorting_builder", "sorting", "python", "encouraging", 0.15, 0.8, 0.25, 240),
        ("sorting_solver", "sorting", "java", "socratic", 0.70, 0.2, 0.08, 110),
        ("graphs_novice", "graphs", "python", "scaffolded", -0.80, 1.8, 0.78, 540),
        ("graphs_builder", "graphs", "javascript", "encouraging", -0.20, 1.3, 0.45, 340),
        ("graphs_solver", "graphs", "java", "socratic", 0.60, 0.3, 0.12, 160),
        (
            "dynamic_programming_novice",
            "dynamic_programming",
            "python",
            "scaffolded",
            -0.95,
            2.0,
            0.90,
            580,
        ),
        (
            "dynamic_programming_builder",
            "dynamic_programming",
            "java",
            "encouraging",
            -0.35,
            1.4,
            0.50,
            380,
        ),
        ("databases_builder", "databases", "javascript", "encouraging", 0.10, 0.8, 0.25, 250),
        ("databases_solver", "databases", "python", "socratic", 0.75, 0.2, 0.06, 100),
        ("cross_topic_explorer", "sorting", "javascript", "socratic", 0.00, 0.7, 0.20, 210),
    )
    learners: list[StubLearner] = []
    for name, focus, language, style, adjustment, hint_rate, failed_ratio, solve_time in specs:
        topic_strengths = {topic: 0.25 for topic in TOPICS}
        topic_strengths[focus] = 0.95
        language_preferences = {item: 0.2 for item in LANGUAGES}
        language_preferences[language] = 0.95
        learners.append(
            StubLearner(
                id=f"stub-{name}",
                archetype=name,
                profile={
                    "language": language,
                    "language_preferences": language_preferences,
                    "hint_depth_ceiling": 3
                    if failed_ratio >= 0.7
                    else 4
                    if hint_rate >= 1.2
                    else 5,
                    "teaching_style": style,
                    "difficulty_adjustment": adjustment,
                    "rolling_hint_rate": hint_rate,
                    "rolling_failed_run_ratio": failed_ratio,
                    "rolling_avg_solve_time_seconds": float(solve_time),
                    "topic_strengths": topic_strengths,
                },
            )
        )
    return learners


def interaction_label(learner: StubLearner, problem: SyntheticProblem) -> int:
    from app.ml.features import effective_skill

    skill = effective_skill(learner.profile)
    strength_map = learner.profile.get("topic_strengths", {})
    strength = (
        float(strength_map.get(problem.topic_tags[0], 0.5))
        if isinstance(strength_map, dict)
        else 0.5
    )
    productive_struggle = strength >= 0.75 and abs(problem.difficulty - skill) <= 1.25

    return int(productive_struggle)


def generate_training_pairs(n_per_user: int = 20) -> list[TrainingPair]:
    """Generate reproducible triples across fake learners and the stub catalog."""
    catalog = synthetic_problem_catalog()
    pairs: list[TrainingPair] = []
    for learner in stub_learners():
        user_vector = tuple(user_feature_vector(learner.profile))
        selected = catalog[: max(1, min(len(catalog), n_per_user * 3))]
        for problem in selected:
            pairs.append(
                TrainingPair(
                    learner_id=learner.id,
                    problem=problem,
                    user_features=user_vector,
                    problem_features=tuple(problem_feature_vector(problem)),
                    label=interaction_label(learner, problem),
                )
            )
    return pairs
