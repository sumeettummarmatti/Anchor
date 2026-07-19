from typing import Any, Optional
from pydantic import BaseModel

class ExecutionStepResponse(BaseModel):
    trace_id: str
    step_number: int
    line_number: Optional[int]
    executed_code: str
    event_type: str
    locals: dict[str, Any]
    globals: dict[str, Any]
    call_stack: list[str]
    stdout: str
    error: Optional[str] = None
    variable_history: dict[str, list[Any]]
