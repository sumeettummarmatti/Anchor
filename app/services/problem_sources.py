"""Fetch public problem metadata for the personalized recommendation catalog."""

from __future__ import annotations

import ast
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, unquote

import httpx

from app.ml.data.synthetic_problems import SyntheticProblem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProblemCandidate:
    problem: SyntheticProblem
    provider: str
    url: str


@dataclass(frozen=True)
class GitHubProblemEntry:
    problem_id: str
    number: int
    title: str
    difficulty: str
    solution_path: str
    solution_url: str
    raw_url: str


class ProblemSourceService:
    """Load a small cached pool of real public problems from supported sources."""

    _cache: tuple[float, tuple[ProblemCandidate, ...]] | None = None
    _detail_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _github_index: dict[str, GitHubProblemEntry] = {}
    _cache_ttl_seconds = 900.0
    _github_repo = "Garvit244/Leetcode"
    _github_branch = "master"
    _github_provider = "GitHub · Garvit244/Leetcode"

    @classmethod
    def _github_readme_url(cls) -> str:
        return f"https://raw.githubusercontent.com/{cls._github_repo}/{cls._github_branch}/README.md"

    @classmethod
    def _github_file_url(cls, path: str) -> str:
        encoded_path = quote(path, safe="/_-.()")
        return f"https://github.com/{cls._github_repo}/blob/{cls._github_branch}/{encoded_path}"

    @classmethod
    def _github_raw_url(cls, path: str) -> str:
        encoded_path = quote(path, safe="/_-.()")
        return f"https://raw.githubusercontent.com/{cls._github_repo}/{cls._github_branch}/{encoded_path}"

    async def fetch_details(self, problem_id: str) -> dict[str, Any]:
        normalized_id = problem_id.strip()
        if normalized_id.startswith("github-leetcode-"):
            return await self.fetch_github_leetcode_details(
                normalized_id.removeprefix("github-leetcode-")
            )
        raise ValueError("Unsupported problem source.")

    async def fetch(self) -> list[ProblemCandidate]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < self._cache_ttl_seconds:
            return list(self._cache[1])

        headers = {"User-Agent": "MentorLab/1.0 (educational recommendation client)"}
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as client:
            try:
                candidates = await self._fetch_github_leetcode(client)
            except Exception as exc:
                logger.warning("github_problem_source_unavailable", extra={"error": str(exc)})
                candidates = []

        deduplicated: dict[str, ProblemCandidate] = {}
        for candidate in candidates:
            deduplicated.setdefault(candidate.problem.id, candidate)
        loaded = tuple(deduplicated.values())
        if loaded:
            self._cache = (now, loaded)
        return list(loaded)

    async def _fetch_github_leetcode(
        self, client: httpx.AsyncClient
    ) -> list[ProblemCandidate]:
        entries = await self._load_github_index(client)
        return [
            ProblemCandidate(
                problem=SyntheticProblem(
                    id=entry.problem_id,
                    title=entry.title,
                    topic_tags=self._github_topic_tags(entry.title),
                    difficulty=self._github_difficulty(entry.difficulty),
                    language="python",
                ),
                provider=self._github_provider,
                url=entry.solution_url,
            )
            for entry in entries
        ]

    async def _load_github_index(
        self, client: httpx.AsyncClient
    ) -> list[GitHubProblemEntry]:
        if self._github_index:
            return list(self._github_index.values())

        response = await client.get(self._github_readme_url())
        response.raise_for_status()
        entries = self._parse_github_readme(response.text)
        if not entries:
            raise ValueError("The GitHub problem index did not contain any Python solutions.")
        self._github_index = {entry.problem_id: entry for entry in entries}
        return entries

    @classmethod
    def _parse_github_readme(cls, readme: str) -> list[GitHubProblemEntry]:
        entries: dict[str, GitHubProblemEntry] = {}
        for line in readme.splitlines():
            number_match = re.match(r"\s*\|?\s*(\d{1,4})\s*\|", line)
            if not number_match:
                continue
            links = re.findall(r"\[([^]]+)\]\(([^)]+)\)", line)
            title_link = next(
                (
                    (text.strip(), href.strip())
                    for text, href in links
                    if text.strip().lower() not in {"python", "solution"}
                    and not href.strip().lower().endswith(".py")
                ),
                None,
            )
            solution_link = next(
                (
                    href.strip()
                    for text, href in links
                    if text.strip().lower() == "python" or href.strip().lower().endswith(".py")
                ),
                None,
            )
            difficulty_match = re.search(r"\b(Easy|Medium|Hard)\b", line, flags=re.IGNORECASE)
            if not title_link or not solution_link or not difficulty_match:
                continue
            number = int(number_match.group(1))
            title, solution_path = title_link[0], cls._github_solution_path(solution_link)
            if not solution_path:
                continue
            problem_id = f"github-leetcode-{number}"
            entries[problem_id] = GitHubProblemEntry(
                problem_id=problem_id,
                number=number,
                title=title,
                difficulty=difficulty_match.group(1).title(),
                solution_path=solution_path,
                solution_url=cls._github_file_url(solution_path),
                raw_url=cls._github_raw_url(solution_path),
            )
        return list(entries.values())

    @staticmethod
    def _github_solution_path(link: str) -> str:
        value = unquote(link.strip())
        github_match = re.search(
            r"github\.com/Garvit244/Leetcode/(?:blob|raw)/[^/]+/(.+)$",
            value,
            flags=re.IGNORECASE,
        )
        if github_match:
            value = github_match.group(1)
        if value.startswith(("http://", "https://")):
            return ""
        return value.removeprefix("./").lstrip("/")

    async def fetch_github_leetcode_details(self, problem_number: str) -> dict[str, Any]:
        if not re.fullmatch(r"\d{1,4}", problem_number):
            raise ValueError("Invalid GitHub LeetCode problem number.")

        problem_id = f"github-leetcode-{int(problem_number)}"
        cached = self._detail_cache.get(problem_id)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl_seconds:
            return dict(cached[1])

        headers = {"User-Agent": "MentorLab/1.0 (educational recommendation client)"}
        timeout = httpx.Timeout(8.0, connect=3.0)
        async with httpx.AsyncClient(
            headers=headers, timeout=timeout, follow_redirects=True
        ) as client:
            entries = await self._load_github_index(client)
            entry = self._github_index.get(problem_id)
            if entry is None:
                entry = next((item for item in entries if item.problem_id == problem_id), None)
            if entry is None:
                raise ValueError("GitHub LeetCode solution was not found.")
            response = await client.get(entry.raw_url)
            response.raise_for_status()

        source = response.text
        statement = self._github_statement(source)
        code = self._github_starter_code(source)
        detail = {
            "id": entry.problem_id,
            "title": entry.title,
            "title_slug": f"github-leetcode-{entry.number}",
            "content": statement,
            "topic_tags": list(self._topic_tags([entry.title])),
            "difficulty": entry.difficulty,
            "language": "python",
            "hints": [],
            "code_snippets": [
                {"lang": "Python", "lang_slug": "python", "code": code}
            ],
            "provider": self._github_provider,
            "url": entry.solution_url,
        }
        self._detail_cache[problem_id] = (now, detail)
        return dict(detail)

    @staticmethod
    def _github_statement(source: str) -> str:
        try:
            module = ast.parse(source)
            statement = ast.get_docstring(module, clean=True)
        except SyntaxError:
            statement = None
        return statement or "Problem statement is documented in the linked GitHub solution."

    @staticmethod
    def _github_starter_code(source: str) -> str:
        try:
            module = ast.parse(source)
        except SyntaxError:
            return ""

        lines = source.splitlines()
        edits: list[tuple[int, int, list[str]]] = []

        module_docstring = ast.get_docstring(module, clean=False)
        if module_docstring and module.body and isinstance(module.body[0], ast.Expr):
            docstring = module.body[0]
            edits.append((docstring.lineno - 1, docstring.end_lineno, []))

        functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

        def collect_functions(node: ast.AST, inside_function: bool = False) -> None:
            is_function = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_function and not inside_function:
                functions.append(node)
            for child in ast.iter_child_nodes(node):
                collect_functions(child, inside_function or is_function)

        collect_functions(module)
        for function in functions:
            if not function.body:
                continue

            function_docstring = ast.get_docstring(function, clean=False)
            first_statement = function.body[0]
            has_docstring = function_docstring is not None
            body_indent = " " * (function.col_offset + 4)
            if has_docstring:
                docstring = first_statement
                if len(function.body) == 1:
                    edits.append((docstring.end_lineno, docstring.end_lineno, [body_indent + "pass"]))
                    continue
                body_start = function.body[1].lineno - 1
            else:
                body_start = first_statement.lineno - 1
            edits.append((body_start, function.end_lineno, [body_indent + "pass"]))

        for start, end, replacement in sorted(edits, reverse=True):
            lines[start:end] = replacement
        return "\n".join(lines).strip()

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
    def _github_difficulty(value: Any) -> int:
        return {"Easy": 1, "Medium": 3, "Hard": 5}.get(str(value), 3)

    @classmethod
    def _github_topic_tags(cls, title: str) -> tuple[str, ...]:
        tags = tuple(tag for tag in cls._topic_tags([title]) if tag.casefold() != title.casefold())
        return tags or ("general",)
