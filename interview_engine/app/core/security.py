"""Small swappable authentication boundary for the local prototype."""

from typing import Optional
from fastapi import Header, HTTPException
from .config import settings

def validate_external_identity(user_id: str) -> str:
    if not user_id.strip():
        raise ValueError("user_id must not be blank")
    return user_id

def get_authenticated_user(
    x_api_key: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
) -> str:
    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-ID")
    try:
        return validate_external_identity(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
