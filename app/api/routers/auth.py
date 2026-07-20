from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_jwt
from app.db.session import get_db_session
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.oauth_service import OAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _establish_session(request: Request, tokens: TokenResponse, settings: Settings) -> None:
    claims = decode_jwt(tokens.access_token, settings, "access")
    request.session["user_id"] = str(claims["sub"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    user = await AuthService(session, settings).register(
        payload.email, payload.password, payload.display_name
    )
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    tokens = await AuthService(session, settings).login(payload.email, payload.password)
    _establish_session(request, tokens, settings)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    tokens = await AuthService(session, settings).refresh(payload.refresh_token)
    _establish_session(request, tokens, settings)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        await AuthService(session, settings).logout(payload.refresh_token)
    finally:
        request.session.clear()


@router.get("/oauth/{provider}/login", summary="Begin Google or GitHub OAuth")
async def oauth_login(provider: str, request: Request, settings: Settings = Depends(get_settings)):
    return await OAuthService(settings).authorize_redirect(provider, request)


@router.get("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    oauth_id, email, display_name = await OAuthService(settings).fetch_identity(provider, request)
    auth_service = AuthService(session, settings)
    user = await auth_service.get_or_create_oauth_user(provider, oauth_id, email, display_name)
    tokens = await auth_service.issue_oauth_tokens(user)
    _establish_session(request, tokens, settings)
    return tokens
