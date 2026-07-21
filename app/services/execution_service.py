from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AIProviderError, ExecutionTimeoutError
from app.models.execution import ExecutionRun
from app.services.session_service import SessionService
from app.services.static_analysis_service import StaticAnalysisService


class ExecutionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session, self.settings = session, settings

    async def run(self, user_id, payload):  # type: ignore[no-untyped-def]
        if payload.session_id is not None:
            await SessionService(self.session).get(payload.session_id, user_id)
        analysis = await StaticAnalysisService(self.settings).analyze(
            payload.language, payload.code
        )
        version = payload.version
        if version == "*":
            version = "3.10.0"

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.piston_request_timeout_seconds
            ) as client:
                response = await client.post(
                    "https://run.glot.io/languages/python/latest",
                    headers={"Content-type": "application/json"},
                    json={
                        "files": [{"name": "main.py", "content": payload.code}],
                        "stdin": payload.stdin or "",
                    },
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ExecutionTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("Code execution service is unavailable.") from exc

        data = response.json()
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
        error = data.get("error", "")
        # glot.io signals failure via a non-empty `error` field instead of exit code
        exit_code = 0 if not error else 1
        if error and error not in stderr:
            stderr = f"{stderr}\n{error}".strip()

        status = "completed" if exit_code == 0 else "failed"
        execution = ExecutionRun(
            session_id=payload.session_id,
            code_snapshot=payload.code,
            language=payload.language,
            version=version,
            stdin=payload.stdin,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            status=status,
            static_analysis_result=analysis.model_dump(),
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)

        if status == "completed":
            from interview_engine.app.main import get_analytics_event_publisher

            get_analytics_event_publisher().publish(
                event_type="PROBLEM_SOLVED",
                source="execution",
                user_id=str(user_id),
                metadata={
                    "language": payload.language,
                    "session_id": str(payload.session_id) if payload.session_id else None,
                },
            )
        return execution, None, analysis
