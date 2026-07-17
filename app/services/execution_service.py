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
            version = (
                "3.10.0" if payload.language.lower() in {"python", "python3", "py"} else "18.15.0"
            )
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.piston_request_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{self.settings.piston_base_url}/api/v2/execute",
                    json={
                        "language": payload.language,
                        "version": version,
                        "files": [{"content": payload.code}],
                        "stdin": payload.stdin,
                        "compile_timeout": 10000,
                        "run_timeout": 3000,
                    },
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ExecutionTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("Code execution service is unavailable.") from exc
        data = response.json()
        run = data.get("run", {})
        output = run.get("output", "")
        execution = ExecutionRun(
            session_id=payload.session_id,
            code_snapshot=payload.code,
            language=payload.language,
            version=version,
            stdin=payload.stdin,
            stdout=run.get("stdout", output),
            stderr=run.get("stderr", ""),
            exit_code=run.get("code"),
            status="completed" if run.get("code") == 0 else "failed",
            static_analysis_result=analysis.model_dump(),
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)
        return execution, run.get("wall_time"), analysis
