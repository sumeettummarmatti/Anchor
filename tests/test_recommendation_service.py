from pathlib import Path
from uuid import UUID

from httpx import AsyncClient

from app.ml.data.synthetic_interactions import stub_learners
from app.ml.data.synthetic_problems import SyntheticProblem
from app.ml.train_recommender import rank_for_learner, train, validate_model
from app.services.problem_sources import ProblemCandidate, ProblemSourceService
from app.services.recommendation_service import RecommendationService
from tests.test_projects import token_for


async def test_recommendations_are_empty_when_github_source_is_unavailable(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RECOMMENDATION_ARTIFACT_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(ProblemSourceService, "fetch", _empty_sources)
    from app.core.config import get_settings

    get_settings.cache_clear()
    tokens = await token_for(client, "recommend-fallback@example.com")
    response = await client.get(
        "/problems/recommended?k=5",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_recommendation_artifacts_load(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(ProblemSourceService, "fetch", _github_sources)
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


async def test_external_problem_is_ranked_and_linked(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    tokens = await token_for(client, "recommend-external@example.com")
    user = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    candidate = ProblemCandidate(
        problem=SyntheticProblem(
            id="github-leetcode-1",
            title="External Graph Problem",
            topic_tags=("graphs",),
            difficulty=3,
            language="python",
        ),
        provider="GitHub · Garvit244/Leetcode",
        url="https://github.com/Garvit244/Leetcode/blob/master/1-100q/TwoSum.py",
    )

    async def fake_fetch(self) -> list[ProblemCandidate]:
        return [candidate]

    monkeypatch.setattr(ProblemSourceService, "fetch", fake_fetch)
    artifact_dir = tmp_path / "recommender"
    train(epochs=2, artifact_dir=artifact_dir)

    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        recommendations = await RecommendationService(
            session, artifact_dir=artifact_dir
        ).get_recommendations(UUID(user.json()["id"]), k=1)

    assert len(recommendations) == 1
    assert recommendations[0].source == "bi_encoder"
    assert recommendations[0].provider == "GitHub · Garvit244/Leetcode"
    assert recommendations[0].url == candidate.url


def test_twenty_stub_learners_produce_personalized_rankings(tmp_path: Path) -> None:
    learners = stub_learners()
    assert len(learners) == 20
    assert len({repr(learner.profile) for learner in learners}) == 20

    model, losses = train(epochs=20, artifact_dir=tmp_path / "recommender")
    validation = validate_model(model, learners)

    assert len(losses) == 20
    assert losses[-1] < losses[0]
    assert validation["learner_count"] == 20
    assert validation["unique_top_k_rankings"] >= 10
    assert validation["focus_topic_hit_rate"] >= 0.5

    novice = next(learner for learner in learners if learner.archetype == "arrays_novice")
    solver = next(learner for learner in learners if learner.archetype == "arrays_solver")
    novice_difficulty = (
        sum(problem.difficulty for _, problem in rank_for_learner(model, novice)) / 5
    )
    solver_difficulty = (
        sum(problem.difficulty for _, problem in rank_for_learner(model, solver)) / 5
    )
    assert solver_difficulty > novice_difficulty


async def _empty_sources(self) -> list[ProblemCandidate]:
    return []


async def _github_sources(self) -> list[ProblemCandidate]:
    return [
        ProblemCandidate(
            problem=SyntheticProblem(
                id=f"github-leetcode-{number}",
                title=f"GitHub problem {number}",
                topic_tags=("arrays",),
                difficulty=number,
                language="python",
            ),
            provider="GitHub · Garvit244/Leetcode",
            url=f"https://github.com/Garvit244/Leetcode/blob/master/{number}.py",
        )
        for number in range(1, 5)
    ]


class _FakeGitHubResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None

class _FakeGitHubClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str, *args, **kwargs) -> _FakeGitHubResponse:
        if url.endswith("README.md"):
            return _FakeGitHubResponse(
                "| 1 | [Two Sum](https://example.com/two-sum) | "
                "[Python](1-100q/TwoSum.py) | Easy |"
            )
        return _FakeGitHubResponse(
            "'''Find two numbers that add up to a target.'''\n\n"
            "class Solution:\n"
            "    def twoSum(self, nums, target):\n"
            "        return [0, 1]\n"
        )


async def test_github_leetcode_details_are_normalized(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.problem_sources.httpx.AsyncClient",
        lambda **kwargs: _FakeGitHubClient(),
    )
    ProblemSourceService._detail_cache.clear()
    ProblemSourceService._github_index.clear()

    detail = await ProblemSourceService().fetch_details("github-leetcode-1")

    assert detail["id"] == "github-leetcode-1"
    assert detail["title"] == "Two Sum"
    assert detail["provider"] == "GitHub · Garvit244/Leetcode"
    assert detail["content"] == "Find two numbers that add up to a target."
    assert detail["code_snippets"] == [
        {
            "lang": "Python",
            "lang_slug": "python",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        pass",
        }
    ]


async def test_problem_details_endpoint_accepts_github_source(
    client: AsyncClient, monkeypatch
) -> None:
    tokens = await token_for(client, "recommend-details@example.com")

    async def fake_fetch_details(self, problem_id: str) -> dict[str, object]:
        assert problem_id == "github-leetcode-1"
        return {
            "id": "github-leetcode-1",
            "title": "Two Sum",
            "title_slug": "github-leetcode-1",
            "content": "Find two numbers that add up to a target.",
            "topic_tags": ["arrays"],
            "difficulty": "Easy",
            "language": "python",
            "code_snippets": [],
            "provider": "GitHub · Garvit244/Leetcode",
            "url": "https://github.com/Garvit244/Leetcode/blob/master/1-100q/TwoSum.py",
        }

    monkeypatch.setattr(ProblemSourceService, "fetch_details", fake_fetch_details)
    response = await client.get(
        "/problems/details/github-leetcode-1",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "GitHub · Garvit244/Leetcode"
    assert response.json()["title"] == "Two Sum"
