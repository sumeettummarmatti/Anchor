from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.execution import ExecutionRequest, ExecutionResult
from app.services.execution_service import ExecutionService

router = APIRouter(prefix="/execution", tags=["execution"])


@router.post("/run", response_model=ExecutionResult)
async def run_code(
    payload: ExecutionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ExecutionResult:
    execution, execution_time_ms, analysis = await ExecutionService(session, settings).run(
        current_user.id, payload
    )
    return ExecutionResult(
        id=execution.id,
        stdout=execution.stdout,
        stderr=execution.stderr,
        exit_code=execution.exit_code,
        status=execution.status,
        execution_time_ms=execution_time_ms,
        static_analysis=analysis,
    )
