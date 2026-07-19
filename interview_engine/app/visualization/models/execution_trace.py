from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

@dataclass
class ExecutionTrace:
    id: str
    language: str
    source_code: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    steps: List["ExecutionStep"] = field(default_factory=list)
    annotations: Dict[int, "AIAnnotation"] = field(default_factory=dict)
    summary: Optional[dict] = None

@dataclass
class ExecutionStep:
    trace_id: str
    step_number: int
    line_number: Optional[int]
    executed_code: str
    event_type: str
    locals: Dict[str, Any]
    globals: Dict[str, Any]
    call_stack: List[str]
    stdout: str
    error: Optional[str] = None
    variable_history: Dict[str, List[Any]] = field(default_factory=dict)

@dataclass
class AIAnnotation:
    trace_id: str
    step_number: int
    explanation: str
    detected_concept: str
    difficulty: str
    provider: str = "local_fallback"
