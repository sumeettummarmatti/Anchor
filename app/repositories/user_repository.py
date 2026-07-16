from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_oauth_identity(self, provider: str, oauth_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
        )
        return result.scalar_one_or_none()

    def add_user(self, user: User) -> None:
        self.session.add(user)

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    def add_refresh_token(self, token: RefreshToken) -> None:
        self.session.add(token)
