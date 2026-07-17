from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent
from app.repositories.hint_repository import HintRepository
from app.schemas.mentor import ExplainErrorRequest, MentorChatRequest, MentorHintRequest
from app.schemas.static_analysis import Diagnostic
from app.services.ai_service import AIService, PromptContext
from app.services.session_service import SessionService


class MentorService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        ai_service: AIService | None = None,
    ) -> None:
        self.session, self.settings = session, settings
        self.ai = ai_service or AIService(settings)

    async def chat(self, user_id: UUID, payload: MentorChatRequest) -> tuple[str, str]:
        diagnostics = await self._ground_diagnostics(
            user_id, payload.session_id, payload.execution_id, payload.diagnostics
        )
        context = PromptContext(
            "chat", payload.language, payload.code, payload.message, tuple(diagnostics)
        )
        return await self.ai.complete(context)

    async def explain_error(self, user_id: UUID, payload: ExplainErrorRequest) -> tuple[str, str]:
        diagnostics = await self._ground_diagnostics(
            user_id, payload.session_id, None, payload.diagnostics
        )
        context = PromptContext(
            "explain_error",
            payload.language,
            payload.code,
            "Explain this error.",
            tuple(diagnostics),
            payload.error,
        )
        return await self.ai.complete(context)

    async def hint(self, user_id: UUID, payload: MentorHintRequest) -> tuple[HintEvent, str]:
        await SessionService(self.session).get(payload.session_id, user_id)
        repository = HintRepository(self.session)
        next_level = (await repository.highest_level(user_id, payload.session_id)) + 1
        if next_level > 5:
            next_level = 5
        if payload.level is not None and payload.level != next_level:
            from app.core.exceptions import ConflictError

            raise ConflictError(f"The next available hint level is {next_level}.")
        diagnostics = await self._ground_diagnostics(
            user_id, payload.session_id, None, payload.diagnostics
        )
        context = PromptContext(
            "hint",
            payload.language,
            payload.code,
            payload.request,
            tuple(diagnostics),
            hint_level=next_level,
        )
        response, model = await self.ai.complete(context)
        event = await repository.create(
            HintEvent(
                user_id=user_id,
                session_id=payload.session_id,
                level=next_level,
                prompt=payload.request,
                response=response,
            )
        )
        return event, model

    async def _ground_diagnostics(
        self,
        user_id: UUID,
        session_id: UUID | None,
        execution_id: UUID | None,
        supplied: list[Diagnostic],
    ) -> list[Diagnostic]:
        if session_id is not None:
            await SessionService(self.session).get(session_id, user_id)
        execution: ExecutionRun | None = None
        if execution_id is not None:
            if session_id is None:
                raise NotFoundError("Execution run not found.")
            result = await self.session.execute(
                select(ExecutionRun).where(ExecutionRun.id == execution_id)
            )
            execution = result.scalar_one_or_none()
            if execution is None or execution.session_id != session_id:
                raise NotFoundError("Execution run not found.")
        elif session_id is not None:
            result = await self.session.execute(
                select(ExecutionRun)
                .where(ExecutionRun.session_id == session_id)
                .order_by(ExecutionRun.created_at.desc())
                .limit(1)
            )
            execution = result.scalar_one_or_none()
        if execution and execution.static_analysis_result:
            return [
                Diagnostic.model_validate(item)
                for item in execution.static_analysis_result.get("diagnostics", [])
            ]
        return supplied
