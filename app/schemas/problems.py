from __future__ import annotations

from pydantic import BaseModel, Field


class ProblemRecommendation(BaseModel):
    id: str
    title: str
    topic_tags: list[str]
    difficulty: int = Field(ge=1, le=5)
    language: str
    score: float
    source: str
    provider: str = "GitHub · Garvit244/Leetcode"
    url: str | None = None


class ProblemCodeSnippet(BaseModel):
    lang: str
    lang_slug: str
    code: str


class ProblemDetail(BaseModel):
    id: str
    title: str
    title_slug: str
    content: str
    topic_tags: list[str]
    difficulty: str
    language: str = "python"
    example_testcases: str | None = None
    hints: list[str] = Field(default_factory=list)
    code_snippets: list[ProblemCodeSnippet] = Field(default_factory=list)
    provider: str = "Problem source"
    url: str
