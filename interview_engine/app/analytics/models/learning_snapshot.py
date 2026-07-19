from dataclasses import dataclass
from typing import Optional


@dataclass
class LearningSnapshot:
    total_problems: int
    total_interviews: int
    average_score: Optional[float]
    favorite_language: Optional[str]
    current_streak: int
    last_active: Optional[str]
