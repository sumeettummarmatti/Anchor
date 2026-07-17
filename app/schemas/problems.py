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
