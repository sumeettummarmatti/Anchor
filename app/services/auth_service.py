from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, email: str, password: str, display_name: str | None) -> User:
        normalized_email = email.lower()
        if await self.users.get_by_email(normalized_email):
            raise ConflictError("An account with this email already exists.")
        user = User(
            email=normalized_email,
            hashed_password=hash_password(password),
            display_name=display_name,
        )
        self.users.add_user(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.users.get_by_email(email.lower())
        if user is None or user.hashed_password is None:
            raise AuthenticationError("Incorrect email or password.")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password.")
        return await self._issue_token_pair(user)

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        try:
            claims = decode_jwt(raw_refresh_token, self.settings, expected_type="refresh")
            user_id = UUID(str(claims["sub"]))
        except (KeyError, ValueError) as exc:
            raise AuthenticationError("Invalid or expired refresh token.") from exc

        stored_token = await self.users.get_refresh_token(hash_refresh_token(raw_refresh_token))
        token_expires_at = stored_token.expires_at if stored_token else None
        if token_expires_at is not None and token_expires_at.tzinfo is None:
            token_expires_at = token_expires_at.replace(tzinfo=UTC)
        if stored_token is None or stored_token.revoked or token_expires_at <= datetime.now(UTC):
            raise AuthenticationError("Refresh token has been revoked or expired.")
        if stored_token.user_id != user_id:
            raise AuthenticationError("Invalid refresh token.")

        stored_token.revoked = True
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User no longer exists.")
        return await self._issue_token_pair(user)

    async def logout(self, raw_refresh_token: str) -> None:
        stored_token = await self.users.get_refresh_token(hash_refresh_token(raw_refresh_token))
        if stored_token is not None:
            stored_token.revoked = True
            await self.session.commit()

    async def get_or_create_oauth_user(
        self, provider: str, oauth_id: str, email: str, display_name: str | None
    ) -> User:
        user = await self.users.get_by_oauth_identity(provider, oauth_id)
        if user is None:
            existing_user = await self.users.get_by_email(email.lower())
            if existing_user is not None:
                existing_user.oauth_provider = provider
                existing_user.oauth_id = oauth_id
                if not existing_user.display_name:
                    existing_user.display_name = display_name
                user = existing_user
            else:
                user = User(
                    email=email.lower(),
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    display_name=display_name,
                )
                self.users.add_user(user)
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def issue_oauth_tokens(self, user: User) -> TokenResponse:
        return await self._issue_token_pair(user)

    async def _issue_token_pair(self, user: User) -> TokenResponse:
        refresh_token, expires_at = create_refresh_token(user.id, self.settings)
        self.users.add_refresh_token(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        return TokenResponse(
            access_token=create_access_token(user.id, self.settings),
            refresh_token=refresh_token,
        )

    async def update_display_name(self, user_id: UUID, display_name: str) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        user.display_name = display_name
        await self.session.commit()
        await self.session.refresh(user)
        return user
