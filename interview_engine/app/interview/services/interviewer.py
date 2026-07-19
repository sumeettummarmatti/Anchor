from typing import Optional

class Interviewer:
    def first_question(self, plan: list[str]) -> str: return plan[0]
    def next_question(self, plan: list[str], index: int) -> Optional[str]:
        return plan[index] if index < len(plan) else None
