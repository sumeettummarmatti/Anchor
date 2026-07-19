from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from .submission_context import SubmissionContext

class InterviewState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    QUESTIONING = "QUESTIONING"
    WAITING_FOR_ANSWER = "WAITING_FOR_ANSWER"
    FOLLOW_UP = "FOLLOW_UP"
    COMPLETED = "COMPLETED"
    REPORT_GENERATED = "REPORT_GENERATED"

class InterviewCreate(BaseModel):
    context: SubmissionContext
    company: Optional[str] = None
    style: str = "Friendly"

class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1)

class InterviewResponse(BaseModel):
    interview_id: str
    first_question: str

class InterviewView(BaseModel):
    id: str
    user_id: str
    submission_id: str
    company: Optional[str]
    difficulty: str
    state: InterviewState
    current_question: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    question_count: int
    planned_question_index: int = 0
    total_turns: int = 0
    consecutive_followups: int = 0
