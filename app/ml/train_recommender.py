"""Train and export the local synthetic recommendation model.

Run with: ``uv run python -m app.ml.train_recommender --epochs 20``.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from app.ml.data.synthetic_interactions import StubLearner, generate_training_pairs, stub_learners
from app.ml.data.synthetic_problems import SyntheticProblem, synthetic_problem_catalog
from app.ml.features import problem_feature_vector, user_feature_vector
from app.ml.models.bi_encoder import BiEncoder

DEFAULT_ARTIFACT_DIR = Path("artifacts/recommender")


def train(epochs: int, artifact_dir: Path) -> tuple[BiEncoder, list[float]]:
    pairs = generate_training_pairs()
    positives = [
        (list(pair.user_features), list(pair.problem_features)) for pair in pairs if pair.label == 1
    ]
    first = pairs[0]
    model = BiEncoder.create(
        len(first.user_features), len(first.problem_features), embedding_dim=16
    )
    losses = model.fit(positives, epochs=epochs)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "bi_encoder.json").write_text(json.dumps(model.state_dict()), encoding="utf-8")

    catalog = synthetic_problem_catalog()
    embeddings = [model.encode_problem(problem_feature_vector(problem)) for problem in catalog]
    (artifact_dir / "problem_embeddings.json").write_text(json.dumps(embeddings), encoding="utf-8")
    (artifact_dir / "problem_index.json").write_text(
        json.dumps([problem.id for problem in catalog]), encoding="utf-8"
    )
    return model, losses


def rank_for_learner(
    model: BiEncoder, learner: StubLearner, k: int = 5
) -> list[tuple[float, SyntheticProblem]]:
    """Rank the synthetic catalog for one learner profile."""
    user_embedding = model.encode_user(user_feature_vector(learner.profile))
    ranked = sorted(
        (
            (
                sum(
                    left * right
                    for left, right in zip(
                        user_embedding,
                        model.encode_problem(problem_feature_vector(problem)),
                        strict=True,
                    )
                ),
                problem,
            )
            for problem in synthetic_problem_catalog()
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    return ranked[: max(1, min(k, len(ranked)))]


def validate_model(
    model: BiEncoder, learners: list[StubLearner] | None = None, k: int = 5
) -> dict[str, object]:
    """Validate finite, non-empty, learner-specific rankings before serving artifacts."""
    learners = learners or stub_learners()
    rankings = {learner.archetype: rank_for_learner(model, learner, k) for learner in learners}
    if not rankings or any(len(items) != k for items in rankings.values()):
        raise ValueError("The recommender returned an empty or incomplete ranking.")
    if any(not math.isfinite(score) for items in rankings.values() for score, _ in items):
        raise ValueError("The recommender returned a non-finite score.")

    signatures = {tuple(problem.id for _, problem in items) for items in rankings.values()}
    focus_hits = 0
    for learner in learners:
        strengths = learner.profile.get("topic_strengths", {})
        focus = max(strengths, key=strengths.get) if isinstance(strengths, dict) else None
        if focus and any(focus in problem.topic_tags for _, problem in rankings[learner.archetype]):
            focus_hits += 1
    focus_hit_rate = focus_hits / len(learners)
    if len(signatures) < max(8, len(learners) // 2) or focus_hit_rate < 0.5:
        raise ValueError(
            "The recommender is not sufficiently personalized: "
            f"{len(signatures)} unique rankings, {focus_hit_rate:.0%} focus-topic hit rate."
        )
    return {
        "learner_count": len(learners),
        "unique_top_k_rankings": len(signatures),
        "focus_topic_hit_rate": round(focus_hit_rate, 3),
        "rankings": rankings,
    }


def _top_titles(
    model: BiEncoder, profile: dict[str, object], k: int = 5
) -> list[tuple[str, int, float]]:
    learner = StubLearner("preview", "preview", profile)
    ranked = rank_for_learner(model, learner, k)
    return [(problem.title, problem.difficulty, round(score, 3)) for score, problem in ranked[:k]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    model, losses = train(max(1, args.epochs), args.artifact_dir)
    learners = stub_learners()
    validation = validate_model(model, learners)
    print(f"trained learners: {validation['learner_count']}")
    print(f"final train loss: {losses[-1]:.4f}")
    print(f"unique top-5 rankings: {validation['unique_top_k_rankings']}")
    print(f"focus-topic hit rate: {validation['focus_topic_hit_rate']:.0%}")
    for learner in learners:
        print(f"{learner.archetype} top-5:")
        for title, difficulty, score in _top_titles(model, learner.profile):
            print(f"  {difficulty}/5  {score:+.3f}  {title}")


if __name__ == "__main__":
    main()
