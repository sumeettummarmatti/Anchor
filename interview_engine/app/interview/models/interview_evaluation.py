from dataclasses import dataclass

@dataclass
class InterviewEvaluation:
    id: str
    interview_id: str
    question_number: int
    evaluation: dict
