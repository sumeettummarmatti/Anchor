"""A dependency-light two-tower bi-encoder.

The model intentionally uses only the Python standard library: it is small enough for local
CPU training and keeps the API install quick. Each tower is a learned linear projection followed
by L2 normalization. In-batch negatives are appropriate at this data scale because every other
problem in a positive batch supplies a useful contrast without a large explicit negative set.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _normalize(values: list[float]) -> tuple[list[float], float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values], norm


@dataclass
class LinearTower:
    input_dim: int
    embedding_dim: int
    weights: list[list[float]]
    bias: list[float]

    @classmethod
    def create(cls, input_dim: int, embedding_dim: int, rng: random.Random) -> LinearTower:
        scale = 1.0 / math.sqrt(input_dim)
        return cls(
            input_dim=input_dim,
            embedding_dim=embedding_dim,
            weights=[
                [rng.uniform(-scale, scale) for _ in range(input_dim)] for _ in range(embedding_dim)
            ],
            bias=[0.0 for _ in range(embedding_dim)],
        )

    def raw(self, features: list[float]) -> list[float]:
        return [
            self.bias[row] + _dot(self.weights[row], features) for row in range(self.embedding_dim)
        ]

    def encode(self, features: list[float]) -> tuple[list[float], list[float], float]:
        raw = self.raw(features)
        normalized, norm = _normalize(raw)
        return normalized, raw, norm

    def state_dict(self) -> dict[str, Any]:
        return {
            "input_dim": self.input_dim,
            "embedding_dim": self.embedding_dim,
            "weights": self.weights,
            "bias": self.bias,
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> LinearTower:
        return cls(
            input_dim=int(state["input_dim"]),
            embedding_dim=int(state["embedding_dim"]),
            weights=[[float(value) for value in row] for row in state["weights"]],
            bias=[float(value) for value in state["bias"]],
        )


class BiEncoder:
    def __init__(self, user_tower: LinearTower, problem_tower: LinearTower) -> None:
        self.user_tower = user_tower
        self.problem_tower = problem_tower

    @classmethod
    def create(
        cls, user_input_dim: int, problem_input_dim: int, embedding_dim: int = 16, seed: int = 7
    ) -> BiEncoder:
        rng = random.Random(seed)
        return cls(
            LinearTower.create(user_input_dim, embedding_dim, rng),
            LinearTower.create(problem_input_dim, embedding_dim, rng),
        )

    def encode_user(self, features: list[float]) -> list[float]:
        return self.user_tower.encode(features)[0]

    def encode_problem(self, features: list[float]) -> list[float]:
        return self.problem_tower.encode(features)[0]

    def state_dict(self) -> dict[str, Any]:
        return {
            "user_tower": self.user_tower.state_dict(),
            "problem_tower": self.problem_tower.state_dict(),
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> BiEncoder:
        return cls(
            LinearTower.from_state_dict(state["user_tower"]),
            LinearTower.from_state_dict(state["problem_tower"]),
        )

    def fit(
        self,
        positive_pairs: list[tuple[list[float], list[float]]],
        *,
        epochs: int = 20,
        batch_size: int = 32,
        learning_rate: float = 0.08,
        temperature: float = 0.15,
    ) -> list[float]:
        """Train with an InfoNCE objective and return mean loss per epoch."""
        if not positive_pairs:
            return []
        losses: list[float] = []
        for _ in range(epochs):
            epoch_loss = 0.0
            batches = 0
            for start in range(0, len(positive_pairs), batch_size):
                batch = positive_pairs[start : start + batch_size]
                user_embeddings: list[list[float]] = []
                problem_embeddings: list[list[float]] = []
                user_raw: list[list[float]] = []
                problem_raw: list[list[float]] = []
                user_norms: list[float] = []
                problem_norms: list[float] = []
                for user_features, problem_features in batch:
                    user, raw_user, norm_user = self.user_tower.encode(user_features)
                    problem, raw_problem, norm_problem = self.problem_tower.encode(problem_features)
                    user_embeddings.append(user)
                    problem_embeddings.append(problem)
                    user_raw.append(raw_user)
                    problem_raw.append(raw_problem)
                    user_norms.append(norm_user)
                    problem_norms.append(norm_problem)

                logits = [
                    [_dot(user, problem) / temperature for problem in problem_embeddings]
                    for user in user_embeddings
                ]
                probabilities: list[list[float]] = []
                for row in logits:
                    maximum = max(row)
                    exponentials = [math.exp(value - maximum) for value in row]
                    denominator = sum(exponentials)
                    probabilities.append([value / denominator for value in exponentials])
                epoch_loss += sum(
                    -math.log(max(probabilities[i][i], 1e-12)) for i in range(len(batch))
                )
                batches += 1

                grad_users = [[0.0] * self.user_tower.embedding_dim for _ in batch]
                grad_problems = [[0.0] * self.problem_tower.embedding_dim for _ in batch]
                for i, row in enumerate(probabilities):
                    for j, probability in enumerate(row):
                        gradient = (probability - (1.0 if i == j else 0.0)) / temperature
                        for dimension in range(self.user_tower.embedding_dim):
                            grad_users[i][dimension] += gradient * problem_embeddings[j][dimension]
                            grad_problems[j][dimension] += gradient * user_embeddings[i][dimension]

                user_grad_w = [
                    [0.0] * self.user_tower.input_dim for _ in range(self.user_tower.embedding_dim)
                ]
                user_grad_b = [0.0] * self.user_tower.embedding_dim
                problem_grad_w = [
                    [0.0] * self.problem_tower.input_dim
                    for _ in range(self.problem_tower.embedding_dim)
                ]
                problem_grad_b = [0.0] * self.problem_tower.embedding_dim
                for index, (user_features, problem_features) in enumerate(batch):
                    user_back = self._normalization_gradient(
                        grad_users[index], user_embeddings[index], user_norms[index]
                    )
                    problem_back = self._normalization_gradient(
                        grad_problems[index], problem_embeddings[index], problem_norms[index]
                    )
                    for dimension, gradient in enumerate(user_back):
                        user_grad_b[dimension] += gradient
                        for feature_index, feature in enumerate(user_features):
                            user_grad_w[dimension][feature_index] += gradient * feature
                    for dimension, gradient in enumerate(problem_back):
                        problem_grad_b[dimension] += gradient
                        for feature_index, feature in enumerate(problem_features):
                            problem_grad_w[dimension][feature_index] += gradient * feature

                scale = learning_rate / len(batch)
                self._apply(self.user_tower, user_grad_w, user_grad_b, scale)
                self._apply(self.problem_tower, problem_grad_w, problem_grad_b, scale)
            losses.append(epoch_loss / max(batches * batch_size, 1))
        return losses

    @staticmethod
    def _normalization_gradient(
        gradient: list[float], normalized: list[float], norm: float
    ) -> list[float]:
        projection = sum(gradient[i] * normalized[i] for i in range(len(gradient)))
        return [(gradient[i] - normalized[i] * projection) / norm for i in range(len(gradient))]

    @staticmethod
    def _apply(
        tower: LinearTower,
        gradient_weights: list[list[float]],
        gradient_bias: list[float],
        scale: float,
    ) -> None:
        for row in range(tower.embedding_dim):
            tower.bias[row] -= scale * gradient_bias[row]
            for column in range(tower.input_dim):
                tower.weights[row][column] -= scale * gradient_weights[row][column]
