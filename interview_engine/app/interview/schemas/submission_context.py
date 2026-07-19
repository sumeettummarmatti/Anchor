from pydantic import BaseModel, Field

class SubmissionContext(BaseModel):
    submission_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    problem_title: str = Field(min_length=1)
    problem_description: str = Field(min_length=1)
    language: str = Field(min_length=1)
    code: str = Field(min_length=1)
    execution_result: str = Field(min_length=1)
    hint_count: int = Field(ge=0)
    attempt_count: int = Field(ge=1)
    difficulty: str = Field(min_length=1)
