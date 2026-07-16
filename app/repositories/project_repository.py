from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import LearningSession, Project, ProjectFile


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_project(self, project_id: UUID, user_id: UUID) -> Project | None:
        result = await self.session.execute(
            select(Project).where(Project.id == project_id, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_projects(self, user_id: UUID) -> list[Project]:
        result = await self.session.execute(
            select(Project).where(Project.user_id == user_id).order_by(Project.updated_at.desc())
        )
        return list(result.scalars())

    async def get_file(self, file_id: UUID, user_id: UUID) -> ProjectFile | None:
        result = await self.session.execute(
            select(ProjectFile)
            .join(Project)
            .where(ProjectFile.id == file_id, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_files(self, project_id: UUID) -> list[ProjectFile]:
        result = await self.session.execute(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.path)
        )
        return list(result.scalars())

    async def get_session(self, session_id: UUID, user_id: UUID) -> LearningSession | None:
        result = await self.session.execute(
            select(LearningSession).where(
                LearningSession.id == session_id, LearningSession.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
