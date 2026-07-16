from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    language: str = Field(min_length=1, max_length=64)


class ProjectUpdate(ProjectCreate):
    pass


class ProjectResponse(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class FileCreate(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    content: str = Field(default="", max_length=200_000)


class FileUpdate(BaseModel):
    content: str = Field(max_length=200_000)


class FileResponse(FileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    updated_at: datetime
