from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.projects import (
    FileCreate,
    FileResponse,
    FileUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await ProjectService(session).create(current_user.id, payload.name, payload.language)
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)
) -> list[ProjectResponse]:
    return [
        ProjectResponse.model_validate(project)
        for project in await ProjectRepository(session).list_projects(current_user.id)
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await ProjectService(session).get(project_id, current_user.id)
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        await ProjectService(session).update(
            project_id, current_user.id, payload.name, payload.language
        )
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await ProjectService(session).delete(project_id, current_user.id)


@router.post(
    "/{project_id}/files", response_model=FileResponse, status_code=status.HTTP_201_CREATED
)
async def create_file(
    project_id: UUID,
    payload: FileCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    return FileResponse.model_validate(
        await ProjectService(session).create_file(
            project_id, current_user.id, payload.path, payload.content
        )
    )


@router.get("/{project_id}/files", response_model=list[FileResponse])
async def list_files(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FileResponse]:
    await ProjectService(session).get(project_id, current_user.id)
    return [
        FileResponse.model_validate(file)
        for file in await ProjectRepository(session).list_files(project_id)
    ]


@router.patch("/files/{file_id}", response_model=FileResponse)
async def update_file(
    file_id: UUID,
    payload: FileUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    return FileResponse.model_validate(
        await ProjectService(session).update_file(file_id, current_user.id, payload.content)
    )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await ProjectService(session).delete_file(file_id, current_user.id)
