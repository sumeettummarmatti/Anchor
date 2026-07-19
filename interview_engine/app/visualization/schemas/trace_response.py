from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .execution_step import ExecutionStepResponse
from .visualization import TraceSummary

class AnnotationResponse(BaseModel):
    trace_id: str
    step_number: int
    explanation: str
    detected_concept: str
    difficulty: str
    provider: str

class TraceResponse(BaseModel):
    id: str
    language: str
    source_code: str
    created_at: datetime
    steps: list[ExecutionStepResponse]
    summary: Optional[TraceSummary] = None

class StepExplanationResponse(BaseModel):
    step: ExecutionStepResponse
    annotation: AnnotationResponse
