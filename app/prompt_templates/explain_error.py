from __future__ import annotations

from app.services.ai_service import PromptContext


def build(context: PromptContext) -> tuple[str, str]:
    return (
        "Explain the code execution result in plain language, whether it succeeded or failed. "
        "Start by saying what happened, then connect the output or error to the supplied code "
        "and static-analysis diagnostics. Give one or two concrete next steps when useful. "
        "Use the learner adaptation and recent activity to calibrate the explanation, "
        "but prioritize the current run. "
        "If the program succeeded, explain what its output means. Do not rewrite the full program.",
        context.as_prompt(),
    )
