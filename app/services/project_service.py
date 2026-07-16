from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.project import Project, ProjectFile
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectRepository(session)

    async def create(self, user_id: UUID, name: str, language: str) -> Project:
        project = Project(user_id=user_id, name=name, language=language)
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get(self, project_id: UUID, user_id: UUID) -> Project:
        project = await self.projects.get_project(project_id, user_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    async def update(self, project_id: UUID, user_id: UUID, name: str, language: str) -> Project:
        project = await self.get(project_id, user_id)
        project.name, project.language = name, language
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: UUID, user_id: UUID) -> None:
        await self.session.delete(await self.get(project_id, user_id))
        await self.session.commit()

    async def create_file(
        self, project_id: UUID, user_id: UUID, path: str, content: str
    ) -> ProjectFile:
        await self.get(project_id, user_id)
        file = ProjectFile(project_id=project_id, path=path, content=content)
        self.session.add(file)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("A file with this path already exists in the project.") from exc
        await self.session.refresh(file)
        return file

    async def update_file(self, file_id: UUID, user_id: UUID, content: str) -> ProjectFile:
        file = await self.projects.get_file(file_id, user_id)
        if file is None:
            raise NotFoundError("File not found.")
        file.content = content
        await self.session.commit()
        await self.session.refresh(file)
        return file

    async def delete_file(self, file_id: UUID, user_id: UUID) -> None:
        file = await self.projects.get_file(file_id, user_id)
        if file is None:
            raise NotFoundError("File not found.")
        await self.session.delete(file)
        await self.session.commit()
