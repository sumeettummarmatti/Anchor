from pydantic import BaseModel, Field

class InterviewReport(BaseModel):
    interview_id: str
    overall_score: float = Field(ge=0, le=10)
    strengths: list[str]
    weaknesses: list[str]
    communication_feedback: str
    recommended_topics: list[str]
    improvement_plan: list[str]
    summary: str
    provider_used: str = "fallback"
