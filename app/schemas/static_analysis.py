from __future__ import annotations

from pydantic import BaseModel, Field


class Diagnostic(BaseModel):
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    severity: str = Field(pattern="^(error|warning|info)$")
    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


class StaticAnalysisRequest(BaseModel):
    language: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=200_000)


class StaticAnalysisResult(BaseModel):
    language: str
    analyzer: str
    available: bool
    diagnostics: list[Diagnostic] = Field(default_factory=list)
