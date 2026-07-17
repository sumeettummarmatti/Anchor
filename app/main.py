from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routers.auth import router as auth_router
from app.api.routers.execution import router as execution_router
from app.api.routers.health import router as health_router
from app.api.routers.mentor import router as mentor_router
from app.api.routers.problems import router as problems_router
from app.api.routers.projects import router as projects_router
from app.api.routers.sessions import router as sessions_router
from app.api.routers.static_analysis import router as static_analysis_router
from app.api.routers.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)
settings = get_settings()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend-only coding mentor API",
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    https_only=not settings.debug,
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(problems_router)
app.include_router(sessions_router)
app.include_router(execution_router)
app.include_router(static_analysis_router)
app.include_router(mentor_router)
app.mount("/demo", StaticFiles(directory="app/static", html=True), name="demo")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    logger.warning("application_error", status_code=exc.status_code, detail=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
