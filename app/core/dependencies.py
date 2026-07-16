from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_jwt
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    try:
        claims = decode_jwt(token, settings, expected_type="access")
        user_id = UUID(str(claims["sub"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise AuthenticationError("User no longer exists.")
    return user
