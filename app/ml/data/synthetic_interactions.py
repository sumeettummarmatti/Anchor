"""SYNTHETIC DATA — replace with real interaction logs once Phase 11 has volume.

Do not let this module's assumptions leak into production feature engineering without review.
The labels are rule-derived rather than random so a small recommendation model can learn a
directional signal during local development.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ml.data.synthetic_problems import SyntheticProblem, synthetic_problem_catalog
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
    common = {"language": "python"}
    return [
        StubLearner(
            "stub-fast-clean-solver",
            "fast_clean_solver",
            {
                **common,
                "hint_depth_ceiling": 5,
                "teaching_style": "socratic",
                "difficulty_adjustment": 0.8,
                "rolling_hint_rate": 0.2,
                "rolling_failed_run_ratio": 0.05,
                "rolling_avg_solve_time_seconds": 90.0,
                "topic_strengths": {
                    topic: 0.85 for topic in ("arrays", "strings", "hashing", "sorting")
                },
            },
        ),
        StubLearner(
            "stub-steady-builder",
            "steady_builder",
            {
                **common,
                "hint_depth_ceiling": 4,
                "teaching_style": "encouraging",
                "difficulty_adjustment": 0.0,
                "rolling_hint_rate": 0.9,
                "rolling_failed_run_ratio": 0.3,
                "rolling_avg_solve_time_seconds": 260.0,
            },
        ),
        StubLearner(
            "stub-frequent-stuck",
            "frequent_stuck",
            {
                **common,
                "hint_depth_ceiling": 3,
                "teaching_style": "scaffolded",
                "difficulty_adjustment": -0.8,
                "rolling_hint_rate": 1.8,
                "rolling_failed_run_ratio": 0.8,
                "rolling_avg_solve_time_seconds": 520.0,
                "topic_strengths": {
                    topic: 0.3 for topic in ("graphs", "dynamic_programming", "recursion")
                },
            },
        ),
    ]


def interaction_label(learner: StubLearner, problem: SyntheticProblem) -> int:
    from app.ml.features import effective_skill

    skill = effective_skill(learner.profile)
    strength_map = learner.profile.get("topic_strengths", {})
    strength = (
        float(strength_map.get(problem.topic_tags[0], 0.5))
        if isinstance(strength_map, dict)
        else 0.5
    )
    productive_struggle = abs(problem.difficulty - skill) <= 1.1 and 0.2 <= strength <= 0.9
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
