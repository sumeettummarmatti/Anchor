from __future__ import annotations

from app.services.ai_service import PromptContext


def build(context: PromptContext) -> tuple[str, str]:
    level_rules = {
        1: "Give one small directional question; do not name the fix.",
        2: "Point to the relevant concept or code area, without implementation details.",
        3: "Describe a concrete next step, but do not write code for the learner.",
        4: "Give a near-complete algorithm or pseudocode, but no full solution.",
        5: "The learner has unlocked this level. Give a complete, explained solution.",
    }
    return (
        "You are a patient coding mentor. " + level_rules[context.hint_level or 1],
        context.as_prompt(),
    )
