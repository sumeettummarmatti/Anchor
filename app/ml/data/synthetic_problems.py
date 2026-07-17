"""Deterministic stub problem catalog for recommendation prototyping.

This catalog is deliberately isolated from the production problem model. Replace it with
real Problem rows once Phase 13 problem management is available.
"""

from __future__ import annotations

from dataclasses import dataclass

TOPICS = (
    "arrays",
    "strings",
    "hashing",
    "recursion",
    "sorting",
    "graphs",
    "dynamic_programming",
    "databases",
)
LANGUAGES = ("python", "javascript", "java")


@dataclass(frozen=True)
class SyntheticProblem:
    id: str
    title: str
    topic_tags: tuple[str, ...]
    difficulty: int
    language: str


def synthetic_problem_catalog() -> list[SyntheticProblem]:
    catalog: list[SyntheticProblem] = []
    number = 1
    for topic_index, topic in enumerate(TOPICS):
        for difficulty in range(1, 7):
            language = LANGUAGES[(topic_index + difficulty) % len(LANGUAGES)]
            catalog.append(
                SyntheticProblem(
                    id=f"stub-problem-{number:03d}",
                    title=f"{topic.replace('_', ' ').title()} challenge {difficulty}",
                    topic_tags=(topic,),
                    difficulty=min(difficulty, 5),
                    language=language,
                )
            )
            number += 1
    return catalog
