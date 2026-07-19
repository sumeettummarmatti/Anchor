from dataclasses import dataclass

@dataclass
class StoredInterviewReport:
    interview_id: str
    report: dict
