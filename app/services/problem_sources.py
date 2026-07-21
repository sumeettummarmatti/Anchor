"""Fetch public problem metadata for the personalized recommendation catalog."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Any

import httpx

from app.ml.data.synthetic_problems import SyntheticProblem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProblemCandidate:
    problem: SyntheticProblem
    provider: str
    url: str


class ProblemSourceService:
    """Load a small cached pool of real public problems from supported sources."""

    _cache: tuple[float, tuple[ProblemCandidate, ...]] | None = None
    _cache_ttl_seconds = 900.0

    async def fetch(self) -> list[ProblemCandidate]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self._cache_ttl_seconds:
            return list(self._cache[1])

        headers = {"User-Agent": "MentorLab/1.0 (educational recommendation client)"}
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as client:
            results = await asyncio.gather(
                self._fetch_codeforces(client),
                self._fetch_leetcode(client),
                self._fetch_cses(client),
                return_exceptions=True,
            )

        candidates: list[ProblemCandidate] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("problem_source_unavailable", extra={"error": str(result)})
                continue
            candidates.extend(result)

        deduplicated: dict[str, ProblemCandidate] = {}
        for candidate in candidates:
            deduplicated.setdefault(candidate.problem.id, candidate)
        loaded = tuple(deduplicated.values())
        if loaded:
            self._cache = (now, loaded)
        return list(loaded)

    async def _fetch_codeforces(self, client: httpx.AsyncClient) -> list[ProblemCandidate]:
        response = await client.get(
            "https://codeforces.com/api/problemset.problems", params={"lang": "en"}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "OK":
            raise ValueError(payload.get("comment", "Codeforces returned an error."))

        candidates: list[ProblemCandidate] = []
        result = payload.get("result") or [[], []]
        for item in result[0][:2000]:
            contest_id = item.get("contestId")
            index = item.get("index")
            title = str(item.get("name") or "").strip()
            if not contest_id or not index or not title:
                continue
            tags = self._topic_tags(item.get("tags", []))
            difficulty = self._codeforces_difficulty(item.get("rating"))
            problem = SyntheticProblem(
                id=f"codeforces-{contest_id}-{index}",
                title=title,
                topic_tags=tags,
                difficulty=difficulty,
                language="python",
            )
            candidates.append(
                ProblemCandidate(
                    problem=problem,
                    provider="Codeforces",
                    url=f"https://codeforces.com/problemset/problem/{contest_id}/{index}",
                )
            )
        return candidates

    async def _fetch_leetcode(self, client: httpx.AsyncClient) -> list[ProblemCandidate]:
        query = """
        query problemsetQuestionList(
          $categorySlug: String
          $limit: Int
          $skip: Int
          $filters: QuestionListFilterInput
        ) {
          problemsetQuestionList: questionList(
            categorySlug: $categorySlug
            limit: $limit
            skip: $skip
            filters: $filters
          ) {
            totalNum
            data {
              difficulty
              isPaidOnly
              title
              titleSlug
              topicTags { name slug }
            }
          }
        }
        """
        response = await client.post(
            "https://leetcode.com/graphql/",
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com/"},
            json={
                "query": query,
                "variables": {"categorySlug": "", "skip": 0, "limit": 100, "filters": {}},
            },
        )
        response.raise_for_status()
        payload = response.json()
        listing = (payload.get("data") or {}).get("problemsetQuestionList") or {}
        candidates: list[ProblemCandidate] = []
        for item in listing.get("data", []):
            if item.get("isPaidOnly") or not item.get("titleSlug") or not item.get("title"):
                continue
            tags = self._topic_tags(
                [tag.get("name", "") for tag in item.get("topicTags", [])]
            )
            problem = SyntheticProblem(
                id=f"leetcode-{item['titleSlug']}",
                title=str(item["title"]),
                topic_tags=tags,
                difficulty=self._leetcode_difficulty(item.get("difficulty")),
                language="python",
            )
            candidates.append(
                ProblemCandidate(
                    problem=problem,
                    provider="LeetCode",
                    url=f"https://leetcode.com/problems/{item['titleSlug']}/",
                )
            )
        return candidates

    async def _fetch_cses(self, client: httpx.AsyncClient) -> list[ProblemCandidate]:
        response = await client.get("https://cses.fi/problemset/list/")
        response.raise_for_status()
        parser = _CSESProblemParser()
        parser.feed(response.text)
        return [
            ProblemCandidate(
                problem=SyntheticProblem(
                    id=f"cses-{problem_id}",
                    title=title,
                    topic_tags=self._topic_tags([section, title]),
                    difficulty=self._cses_difficulty(section),
                    language="python",
                ),
                provider="CSES",
                url=f"https://cses.fi/problemset/task/{problem_id}",
            )
            for problem_id, title, section in parser.problems[:400]
        ]

    @staticmethod
    def _topic_tags(values: list[Any]) -> tuple[str, ...]:
        raw = [str(value).strip() for value in values if str(value).strip()]
        normalized: list[str] = []
        joined = " ".join(raw).lower().replace("_", " ")
        aliases = {
            "array": "arrays",
            "arrays": "arrays",
            "string": "strings",
            "strings": "strings",
            "hash table": "hashing",
            "hashing": "hashing",
            "recursion": "recursion",
            "sorting": "sorting",
            "sort": "sorting",
            "graph": "graphs",
            "graphs": "graphs",
            "dynamic programming": "dynamic_programming",
            "dynamic_programming": "dynamic_programming",
            " dp ": "dynamic_programming",
            "database": "databases",
            "databases": "databases",
            "sql": "databases",
        }
        for alias, topic in aliases.items():
            if alias in f" {joined} " and topic not in normalized:
                normalized.append(topic)
        display_tags = [value for value in raw if value.lower() not in normalized]
        return tuple(dict.fromkeys([*normalized, *display_tags[:3]])) or ("general",)

    @staticmethod
    def _codeforces_difficulty(rating: Any) -> int:
        try:
            value = int(rating)
        except (TypeError, ValueError):
            return 3
        if value <= 1000:
            return 1
        if value <= 1300:
            return 2
        if value <= 1700:
            return 3
        if value <= 2100:
            return 4
        return 5

    @staticmethod
    def _leetcode_difficulty(value: Any) -> int:
        return {"Easy": 1, "Medium": 3, "Hard": 5}.get(str(value), 3)

    @staticmethod
    def _cses_difficulty(section: str) -> int:
        name = section.lower()
        if "advanced" in name:
            return 5
        if any(value in name for value in ("graph", "tree", "range queries", "string")):
            return 4
        if any(value in name for value in ("dynamic", "sorting", "searching")):
            return 3
        if "introductory" in name:
            return 1
        return 2


class _CSESProblemParser:
    """Small HTML parser for the official CSES task index."""

    def __init__(self) -> None:
        self.section = "General"
        self._capture: str | None = None
        self._text: list[str] = []
        self.problems: list[tuple[str, str, str]] = []

    def feed(self, html: str) -> None:
        for token in re.findall(r"<[^>]+>|[^<]+", html, flags=re.DOTALL):
            if token.startswith("<"):
                self._handle_tag(token)
                continue
            if self._capture:
                self._text.append(unescape(token))

    def _handle_tag(self, token: str) -> None:
        heading = re.match(r"</?h[1-4][^>]*>", token, flags=re.IGNORECASE)
        if heading:
            if token.startswith("</"):
                text = " ".join("".join(self._text).split())
                if text:
                    self.section = text
                self._capture = None
                self._text = []
            else:
                self._capture = "heading"
                self._text = []
            return

        link = re.match(
            r'<a[^>]+href=["\'](/problemset/task/(\d+))["\'][^>]*>',
            token,
            flags=re.IGNORECASE,
        )
        if link:
            self._capture = link.group(2)
            self._text = []
        elif token.lower().startswith("</a") and self._capture and self._capture.isdigit():
            title = " ".join("".join(self._text).split())
            if title:
                self.problems.append((self._capture, title, self.section))
            self._capture = None
            self._text = []
