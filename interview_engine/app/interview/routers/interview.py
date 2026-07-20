from fastapi import APIRouter, Depends, HTTPException, Request
from ...core.security import get_authenticated_user
from ...core.llm import request_groq_client
from ..schemas.interview import InterviewCreate, AnswerRequest, InterviewResponse, InterviewView
from ..schemas.evaluation import AnswerResponse
from ..schemas.report import InterviewReport

def create_router(service):
    router = APIRouter(prefix="/interview", tags=["interviews"])

    def owner(interview_id: str, current_user: str):
        try: item = service.require(interview_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        if item.user_id != current_user: raise HTTPException(403, "You do not own this interview")
        return item

    @router.post("/start", response_model=InterviewResponse)
    def start(payload: InterviewCreate, request: Request, current_user: str = Depends(get_authenticated_user)):
        if current_user != payload.context.user_id:
            raise HTTPException(403, "Authenticated user does not own this submission")
        interview = service.start(payload, llm=request_groq_client(request))
        return InterviewResponse(interview_id=interview.id, first_question=interview.current_question)

    @router.post("/{interview_id}/answer", response_model=AnswerResponse)
    def answer(interview_id: str, payload: AnswerRequest, request: Request, current_user: str = Depends(get_authenticated_user)):
        owner(interview_id, current_user)
        try: evaluation, question = service.answer(interview_id, payload.answer, llm=request_groq_client(request))
        except ValueError as exc: raise HTTPException(409, str(exc))
        return AnswerResponse(evaluation=evaluation, next_question=question)

    @router.post("/{interview_id}/finish", response_model=InterviewReport)
    def finish(interview_id: str, request: Request, current_user: str = Depends(get_authenticated_user)):
        owner(interview_id, current_user)
        try: return service.finish(interview_id, llm=request_groq_client(request))
        except ValueError as exc: raise HTTPException(409, str(exc))

    @router.get("/{interview_id}", response_model=InterviewView)
    def get_interview(interview_id: str, current_user: str = Depends(get_authenticated_user)):
        item = owner(interview_id, current_user)
        return InterviewView(id=item.id, user_id=item.user_id, submission_id=item.submission_id, company=item.company, difficulty=item.difficulty, state=item.state, current_question=item.current_question, started_at=item.started_at, completed_at=item.completed_at, question_count=item.question_count, planned_question_index=item.planned_question_index, total_turns=item.total_turns, consecutive_followups=item.consecutive_followups)

    @router.get("/{interview_id}/report", response_model=InterviewReport)
    def get_report(interview_id: str, current_user: str = Depends(get_authenticated_user)):
        owner(interview_id, current_user)
        report = service.repository.get_report(interview_id)
        if not report: raise HTTPException(404, "Report not generated")
        return InterviewReport(**report.report)
    return router
