from __future__ import annotations

from app.services.ai_service import PromptContext


def build(context: PromptContext) -> tuple[str, str]:
    return (
        "Explain the programming error in plain language. Identify its likely source, "
        "then give one or two concrete debugging steps. Do not rewrite the full program.",
        context.as_prompt(),
    )
