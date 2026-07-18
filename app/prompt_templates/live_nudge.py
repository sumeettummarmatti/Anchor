"""Prompt construction for short, non-intrusive Live Tutor nudges."""

from __future__ import annotations

from app.services.ai_service import PromptContext
from app.services.personalization_service import AdaptationContext


def _build_system(adaptation: AdaptationContext | None) -> str:
    lines = [
        "You are Live Tutor, a quiet coding companion.",
        "Respond in at most 2 sentences; never exceed this limit.",
        "Do not reveal the answer directly. Ask a useful question instead.",
        "Never invent code for the learner.",
        "Infer a generic stage: orientation, exploring, pinpoint, or solved.",
        "Return only a JSON object with exactly nudge, nudge_type, and stage.",
        "Do not wrap the JSON in markdown fences or add any commentary.",
        "nudge_type must be orientation, encourage, scaffold, pinpoint, or celebrate.",
    ]
    if adaptation is not None:
        if adaptation.hint_depth_ceiling <= 2:
            lines.append(
                "Be more directive and explicit; this learner benefits from scaffolding."
            )
        if adaptation.teaching_style == "scaffolded":
            lines.append("Prefer concrete directional nudges over open-ended questions.")
        elif adaptation.teaching_style == "socratic":
            lines.append("Prefer open-ended questions over direct suggestions.")
    return " ".join(lines)


def _build_user(context: PromptContext) -> str:
    signal = context.learner_message or "idle pause"
    code = context.code[-3_000:] if context.code else "(empty file)"
    return (
        f"Language: {context.language}\n"
        f"Client signal (soft hint only): {signal}\n"
        f"Current code:\n```{context.language}\n{code}\n```\n"
        "Give one small, Socratic nudge appropriate to the learner's current stage."
    )


def build(context: PromptContext) -> tuple[str, str]:
    return _build_system(context.adaptation), _build_user(context)
