from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class InterviewMessage:
    id: str
    interview_id: str
    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
