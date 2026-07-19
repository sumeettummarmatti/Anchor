from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from ..schemas.interview import InterviewState

@dataclass
class Interview:
    id: str
    user_id: str
    submission_id: str
    context: dict
    company: Optional[str]
    style: str
    difficulty: str
    state: InterviewState = InterviewState.CREATED
    current_question: Optional[str] = None
    questions: list[str] = field(default_factory=list)
    planned_question_index: int = 0
    total_turns: int = 0
    consecutive_followups: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    @property
    def question_count(self): return len(self.questions)

    @property
    def question_index(self):
        """Backward-compatible alias for the planned-question position."""
        return self.planned_question_index
