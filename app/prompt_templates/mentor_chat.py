from __future__ import annotations

from app.services.ai_service import PromptContext


def build(context: PromptContext) -> tuple[str, str]:
    return (
        "You are a patient coding mentor. Teach with concise Socratic questions. "
        "Do not give a complete solution unless the hint level is 5. Ground every claim "
        "in the supplied code, diagnostics, or error output.",
        context.as_prompt(),
    )
