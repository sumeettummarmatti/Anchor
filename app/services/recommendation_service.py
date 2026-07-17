"""Problem recommendations backed by the optional local bi-encoder artifact."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.data.synthetic_problems import SyntheticProblem, synthetic_problem_catalog
from app.ml.features import effective_skill, user_feature_vector
from app.ml.models.bi_encoder import BiEncoder
from app.schemas.problems import ProblemRecommendation
from app.services.personalization_service import PersonalizationService

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self, session: AsyncSession, artifact_dir: str | Path = "artifacts/recommender"
    ) -> None:
        self.session = session
        self.artifact_dir = Path(artifact_dir)
        self._model: BiEncoder | None = None
        self._problem_embeddings: dict[str, list[float]] | None = None

    def _load_artifacts(self) -> bool:
        if self._model is not None and self._problem_embeddings is not None:
            return True
        try:
            model_path = self.artifact_dir / "bi_encoder.json"
            embeddings_path = self.artifact_dir / "problem_embeddings.json"
            index_path = self.artifact_dir / "problem_index.json"
            if not (model_path.exists() and embeddings_path.exists() and index_path.exists()):
                return False
            self._model = BiEncoder.from_state_dict(
                json.loads(model_path.read_text(encoding="utf-8"))
            )
            embeddings = json.loads(embeddings_path.read_text(encoding="utf-8"))
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self._problem_embeddings = {
                str(problem_id): [float(value) for value in embedding]
                for problem_id, embedding in zip(index, embeddings, strict=True)
            }
            return True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("recommendation_artifacts_unavailable", extra={"error": str(exc)})
            self._model = None
            self._problem_embeddings = None
            return False

    async def get_recommendations(self, user_id: UUID, k: int = 5) -> list[ProblemRecommendation]:
        context = await PersonalizationService(self.session).get_context(user_id)
        profile = {**asdict(context), "language": "python"}
        catalog = synthetic_problem_catalog()
        if self._load_artifacts():
            assert self._model is not None
            assert self._problem_embeddings is not None
            user_embedding = self._model.encode_user(user_feature_vector(profile))
            ranked = sorted(
                (
                    (
                        self._cosine(user_embedding, self._problem_embeddings.get(problem.id, [])),
                        problem,
                    )
                    for problem in catalog
                ),
                key=lambda item: item[0],
            )
            source = "bi_encoder"
        else:
            skill = effective_skill(profile)
            ranked = sorted(
                ((-abs(problem.difficulty - skill), problem) for problem in catalog),
                key=lambda item: item[0],
            )
            source = "rule_fallback"
        return [
            self._response(problem, score, source)
            for score, problem in reversed(ranked[-max(1, min(k, len(catalog))) :])
        ]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return -1.0
        return sum(a * b for a, b in zip(left, right, strict=True))

    @staticmethod
    def _response(problem: SyntheticProblem, score: float, source: str) -> ProblemRecommendation:
        return ProblemRecommendation(
            id=problem.id,
            title=problem.title,
            topic_tags=list(problem.topic_tags),
            difficulty=problem.difficulty,
            language=problem.language,
            score=round(float(score), 6),
            source=source,
        )
