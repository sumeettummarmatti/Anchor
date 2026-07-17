from pathlib import Path
from uuid import UUID

from httpx import AsyncClient

from app.ml.data.synthetic_interactions import stub_learners
from app.ml.data.synthetic_problems import synthetic_problem_catalog
from app.ml.features import problem_feature_vector, user_feature_vector
from app.ml.train_recommender import train
from app.services.recommendation_service import RecommendationService
from tests.test_projects import token_for


async def test_recommendations_fall_back_without_artifacts(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RECOMMENDATION_ARTIFACT_DIR", str(tmp_path / "missing"))
    from app.core.config import get_settings

    get_settings.cache_clear()
    tokens = await token_for(client, "recommend-fallback@example.com")
    response = await client.get(
        "/problems/recommended?k=5",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    assert len({item["id"] for item in body}) == 5
    assert {item["source"] for item in body} == {"rule_fallback"}


async def test_recommendation_artifacts_load(client: AsyncClient, tmp_path: Path) -> None:
    tokens = await token_for(client, "recommend-model@example.com")
    user = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    artifact_dir = tmp_path / "recommender"
    train(epochs=2, artifact_dir=artifact_dir)

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        recommendations = await RecommendationService(
            session, artifact_dir=artifact_dir
        ).get_recommendations(UUID(user.json()["id"]), k=4)
    assert len(recommendations) == 4
    assert {item.source for item in recommendations} == {"bi_encoder"}


def test_stub_archetypes_show_directional_recommendations(tmp_path: Path) -> None:
    model, _ = train(epochs=20, artifact_dir=tmp_path / "recommender")
    catalog = synthetic_problem_catalog()
    means: dict[str, float] = {}
    for learner in stub_learners():
        user_embedding = model.encode_user(user_feature_vector(learner.profile))
        ranked = sorted(
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
        )[-5:]
        means[learner.archetype] = sum(item[1].difficulty for item in ranked) / len(ranked)
    assert means["fast_clean_solver"] > means["frequent_stuck"]
