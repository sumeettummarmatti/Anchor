"""Train and export the local synthetic recommendation model.

Run with: ``uv run python -m app.ml.train_recommender --epochs 20``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ml.data.synthetic_interactions import generate_training_pairs, stub_learners
from app.ml.data.synthetic_problems import synthetic_problem_catalog
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


def _top_titles(
    model: BiEncoder, profile: dict[str, object], k: int = 5
) -> list[tuple[str, int, float]]:
    catalog = synthetic_problem_catalog()
    user_embedding = model.encode_user(user_feature_vector(profile))
    ranked = sorted(
        (
            (
                sum(
                    a * b
                    for a, b in zip(
                        user_embedding,
                        model.encode_problem(problem_feature_vector(problem)),
                        strict=True,
                    )
                ),
                problem,
            )
            for problem in catalog
        ),
        key=lambda item: item[0],
    )
    return [
        (problem.title, problem.difficulty, round(score, 3))
        for score, problem in reversed(ranked[-k:])
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    model, losses = train(max(1, args.epochs), args.artifact_dir)
    print(f"final train loss: {losses[-1]:.4f}")
    for learner in stub_learners():
        print(f"{learner.archetype} top-5:")
        for title, difficulty, score in _top_titles(model, learner.profile):
            print(f"  {difficulty}/5  {score:+.3f}  {title}")


if __name__ == "__main__":
    main()
