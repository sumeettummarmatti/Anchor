from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.learner_profile import LearnerProfileResponse
from app.schemas.users import UpdateCurrentUserRequest
from app.services.auth_service import AuthService
from app.services.personalization_service import PersonalizationService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/profile", response_model=LearnerProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LearnerProfileResponse:
    profile = await PersonalizationService(session).ensure_profile(current_user.id)
    return LearnerProfileResponse.model_validate(profile)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UpdateCurrentUserRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    user = await AuthService(session, settings).update_display_name(
        current_user.id, payload.display_name
    )
    return UserResponse.model_validate(user)
