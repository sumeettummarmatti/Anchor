from pydantic import BaseModel, Field
from typing import Optional

class Evaluation(BaseModel):
    technical_accuracy: int = Field(ge=0, le=10)
    communication: int = Field(ge=0, le=10)
    complexity_understanding: int = Field(ge=0, le=10)
    edge_case_reasoning: int = Field(ge=0, le=10)
    confidence: int = Field(ge=0, le=10)
    feedback: str
    provider_used: str = "fallback"

class AnswerResponse(BaseModel):
    evaluation: Evaluation
    next_question: Optional[str]


class AnswerExampleResponse(BaseModel):
    answer: str
    provider_used: str


class NextQuestionResponse(BaseModel):
    next_question: Optional[str]
