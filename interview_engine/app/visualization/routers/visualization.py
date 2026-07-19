from fastapi import APIRouter, Depends, HTTPException
from ...core.security import get_authenticated_user
from ..schemas.visualization import TraceCreate, TraceCreated, TraceSummary
from ..schemas.execution_step import ExecutionStepResponse
from ..schemas.trace_response import AnnotationResponse, StepExplanationResponse, TraceResponse

def step_response(step):
    return ExecutionStepResponse(trace_id=step.trace_id, step_number=step.step_number, line_number=step.line_number, executed_code=step.executed_code, event_type=step.event_type, locals=step.locals, globals=step.globals, call_stack=step.call_stack, stdout=step.stdout, error=step.error, variable_history=step.variable_history)

def create_router(service):
    router = APIRouter(prefix="/visualization", tags=["visualization"])
    auth = Depends(get_authenticated_user)

    @router.post("/trace", response_model=TraceCreated)
    def create_trace(request: TraceCreate, current_user: str = auth):
        try: trace = service.create_trace(request.language, request.source_code, user_id=current_user)
        except (ValueError, SyntaxError) as exc: raise HTTPException(400, str(exc))
        return TraceCreated(trace_id=trace.id)

    @router.get("/{trace_id}", response_model=TraceResponse)
    def get_trace(trace_id: str, current_user: str = auth):
        try: trace = service.get(trace_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        return TraceResponse(id=trace.id, language=trace.language, source_code=trace.source_code, created_at=trace.created_at, steps=[step_response(item) for item in trace.steps], summary=TraceSummary(**trace.summary) if trace.summary else None)

    @router.get("/{trace_id}/steps", response_model=list[ExecutionStepResponse])
    def get_steps(trace_id: str, current_user: str = auth):
        try: trace = service.get(trace_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        return [step_response(item) for item in trace.steps]

    @router.get("/{trace_id}/summary", response_model=TraceSummary)
    def get_summary(trace_id: str, current_user: str = auth):
        try: trace = service.get(trace_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        if not trace.summary: raise HTTPException(404, "Execution summary not found")
        return TraceSummary(**trace.summary)

    @router.get("/{trace_id}/steps/{step_number}", response_model=StepExplanationResponse)
    def explain_step(trace_id: str, step_number: int, current_user: str = auth):
        try: step, annotation = service.explain_step(trace_id, step_number)
        except KeyError as exc: raise HTTPException(404, str(exc))
        return StepExplanationResponse(step=step_response(step), annotation=AnnotationResponse(trace_id=annotation.trace_id, step_number=annotation.step_number, explanation=annotation.explanation, detected_concept=annotation.detected_concept, difficulty=annotation.difficulty, provider=annotation.provider))
    return router
