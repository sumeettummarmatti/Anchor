import json
import logging
from pathlib import Path
from typing import Optional
from ...core.llm import LLMClient, LLMAuthError, LLMCallError, complete_json_with_retry, repair_json_with_retry
from .planner import code_reference

logger = logging.getLogger(__name__)

class FollowupGenerator:
    def __init__(self, llm: Optional[LLMClient] = None, templates_path: Optional[Path] = None):
        self.llm = llm
        path = templates_path or Path(__file__).resolve().parents[1] / "assets" / "followup_templates.json"
        with path.open(encoding="utf-8") as handle:
            self.templates = json.load(handle)

    def generate(self, question: str, answer: str, score: int, context: Optional[dict] = None) -> Optional[str]:
        if score >= 6:
            return None
        if self.llm:
            try:
                result = complete_json_with_retry(self.llm,
                    "Generate one concise technical interview follow-up grounded in the submitted source code, question, and answer. The follow_up must explicitly reference a concrete source-code detail. Return JSON with a non-empty follow_up string.",
                    json.dumps({"question": question, "answer": answer, "score": score, "source_code": (context or {}).get("code", "")}),
                    "followup",
                )
                follow_up = result.get("follow_up")
                if isinstance(follow_up, str) and follow_up.strip():
                    return follow_up.strip()
                logger.error("LLM response/schema failure component=followup detail=missing non-empty follow_up")
                repaired = repair_json_with_retry(self.llm, result, "follow_up: a non-empty string", "followup")
                follow_up = repaired.get("follow_up")
                if isinstance(follow_up, str) and follow_up.strip():
                    return follow_up.strip()
            except LLMAuthError as exc:
                logger.warning("Follow-up generator falling back after LLM authentication failure detail=%s", str(exc)[:240])
            except LLMCallError as exc:
                logger.warning("Follow-up generator falling back after LLM failure type=%s detail=%s", type(exc).__name__, str(exc)[:240])
        text = answer.lower()
        complexity_markers = ("o(", "complexity", "linear", "logarithmic", "space")
        edge_markers = ("edge", "empty", "null", "duplicate", "boundary", "constraint")
        if len(answer.split()) < 12:
            key = "vague"
        elif not any(marker in text for marker in complexity_markers):
            key = "complexity"
        elif not any(marker in text for marker in edge_markers):
            key = "edge_cases"
        else:
            key = "tradeoff"
        if context:
            reference = code_reference(context)
            prompts = {
                "vague": f"In {reference}, describe the exact values or control flow that make your approach work.",
                "complexity": f"Looking at {reference}, which operation determines the time and space complexity?",
                "edge_cases": f"For {reference}, which input edge case would you test first, and how does this code behave?",
                "tradeoff": f"What trade-off does the implementation around {reference} make compared with an alternative?",
            }
            return prompts[key]
        return self.templates[key]
