from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionRequest(BaseModel):
    session_id: UUID | None = None
    code: str = Field(min_length=1, max_length=200_000)
    language: str = Field(min_length=1, max_length=64)
    version: str = Field(default="*", max_length=64)
    stdin: str = Field(default="", max_length=50_000)


class ExecutionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    stdout: str
    stderr: str
    exit_code: int | None
    status: str
    execution_time_ms: int | None = None
