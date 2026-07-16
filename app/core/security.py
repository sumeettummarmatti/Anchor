"""JWT and password helpers. Token issuance is implemented in Phase 2."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def hash_refresh_token(token: str) -> str:
    """Store only a SHA-256 digest of a refresh JWT, never the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encode_jwt(claims: dict[str, object], settings: Settings) -> str:
    return jwt.encode(claims, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    return encode_jwt(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        },
        settings,
    )


def create_refresh_token(user_id: UUID, settings: Settings) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    token = encode_jwt(
        {
            "sub": str(user_id),
            "type": "refresh",
            "jti": str(uuid4()),
            "exp": int(expires_at.timestamp()),
        },
        settings,
    )
    return token, expires_at


def decode_jwt(token: str, settings: Settings, expected_type: str) -> dict[str, object]:
    try:
        claims = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
    if claims.get("type") != expected_type or not claims.get("sub"):
        raise ValueError("Invalid token type.")
    return claims
