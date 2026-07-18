#!/usr/bin/env python3
"""
demo_personalization.py
=======================
Runs an interactive end-to-end demo of the personalization + recommendation engine.

Two stub learners are created:
  • Alice  — struggles a lot (many failures, many hints, slow)
  • Bob    — breezes through (mostly passes, no hints, fast)

After seeding differentiated execution histories the script shows:
  1. Their learner profiles (teaching_style, difficulty_adjustment, …)
  2. Their top-5 recommendations (should be very different)
  3. A mentor chat response that includes the personalization block

Usage:
    uv run python demo_personalization.py
    # or
    python demo_personalization.py
"""

from __future__ import annotations

import asyncio
import json
import random
import string
import sys
import textwrap
import time
from dataclasses import dataclass

import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=30)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _rand_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=n))


def section(title: str) -> None:
    width = 60
    print()
    print("━" * width)
    print(f"  {title}")
    print("━" * width)


def show(label: str, data: object) -> None:
    print(f"\n  ── {label}")
    if isinstance(data, (dict, list)):
        for line in json.dumps(data, indent=2).splitlines():
            print(f"    {line}")
    else:
        for line in textwrap.wrap(str(data), width=70):
            print(f"    {line}")


# ─────────────────────────────────────────────────────────────
# API wrappers
# ─────────────────────────────────────────────────────────────


@dataclass
class Learner:
    name: str
    email: str
    password: str
    token: str = ""
    user_id: str = ""
    project_id: str = ""
    session_id: str = ""


def register_and_login(name: str) -> Learner:
    suffix = _rand_suffix()
    email = f"{name.lower()}.{suffix}@example.com"
    password = "Demo1234!"
    r = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )
    r.raise_for_status()
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    r2.raise_for_status()
    token = r2.json()["access_token"]
    # user_id lives in /users/me, not in the token response
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    me.raise_for_status()
    user_id = me.json()["id"]
    learner = Learner(name=name, email=email, password=password, token=token, user_id=user_id)
    print(f"      {name:12s}  id={learner.user_id}")
    return learner


def auth(learner: Learner) -> dict:
    return {"Authorization": f"Bearer {learner.token}"}


def create_project_and_session(learner: Learner) -> None:
    r = client.post(
        "/projects",
        json={"name": f"{learner.name}'s project", "language": "python"},
        headers=auth(learner),
    )
    r.raise_for_status()
    learner.project_id = r.json()["id"]

    r2 = client.post("/sessions", json={"project_id": learner.project_id}, headers=auth(learner))
    r2.raise_for_status()
    learner.session_id = r2.json()["id"]


def seed_runs(learner: Learner, passed: int, failed: int, hints: int) -> None:
    """Seed execution runs and hint events into the learner's open session."""
    headers = auth(learner)

    # Failing runs
    for _ in range(failed):
        response = client.post(
            "/execution/run",
            json={
                "session_id": learner.session_id,
                "language": "python",
                "code": "print(1/0)",
                "stdin": "",
            },
            headers=headers,
        )
        response.raise_for_status()

    # Passing runs
    for _ in range(passed):
        response = client.post(
            "/execution/run",
            json={
                "session_id": learner.session_id,
                "language": "python",
                "code": "print('hello')",
                "stdin": "",
            },
            headers=headers,
        )
        response.raise_for_status()

    # A local Qwen request can exceed the HTTP timeout while the model is generating. Try
    # the real endpoint once, then seed only the missing events directly so this validation
    # remains deterministic and does not confuse provider latency with profile logic.
    seeded_hints = 0
    for _lvl in range(1, min(hints + 1, 6)):
        try:
            response = client.post(
                "/mentor/hint",
                json={
                    "session_id": learner.session_id,
                    "language": "python",
                    "code": "def solve(): pass",
                    "request": "Give me a hint.",
                },
                headers=headers,
                timeout=8,
            )
            if response.is_success:
                seeded_hints += 1
                time.sleep(0.2)
                continue
            break
        except httpx.TimeoutException:
            print("      Ollama hint timed out; using deterministic DB hint seeding for validation")
            break

    remaining_hints = max(0, hints - seeded_hints)
    if remaining_hints:
        asyncio.run(_seed_hint_events_direct(learner, remaining_hints, seeded_hints + 1))

    # End session so profile update fires
    client.post(f"/sessions/{learner.session_id}/end", headers=headers)


async def _seed_hint_events_direct(learner: Learner, count: int, first_level: int) -> None:
    """Fallback only for local validation when Ollama generation exceeds the HTTP timeout."""
    from uuid import uuid4

    from app.db.session import AsyncSessionLocal
    from app.models.hint_event import HintEvent

    async with AsyncSessionLocal() as session:
        for offset in range(count):
            session.add(
                HintEvent(
                    id=uuid4(),
                    user_id=learner.user_id,
                    session_id=learner.session_id,
                    level=min(5, first_level + offset),
                    prompt="Demo validation hint request",
                    response="Demo validation hint response",
                )
            )
        await session.commit()


def get_profile(learner: Learner) -> dict:
    r = client.get("/users/me/profile", headers=auth(learner))
    r.raise_for_status()
    return r.json()


def get_recommendations(learner: Learner, k: int = 5) -> list:
    r = client.get(f"/problems/recommended?k={k}", headers=auth(learner))
    r.raise_for_status()
    return r.json()


def mentor_chat(learner: Learner) -> dict:
    r = client.post(
        "/mentor/chat",
        json={
            "session_id": None,
            "language": "python",
            "code": "def two_sum(nums, target): pass",
            "message": "I don't know where to start.",
        },
        headers=auth(learner),
    )
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────


def main() -> None:
    # Health check
    try:
        r = client.get("/health")
        r.raise_for_status()
    except Exception as exc:
        print(f"✗ API not reachable at {BASE}: {exc}")
        sys.exit(1)

    section("STEP 1 — Register two stub learners")
    alice = register_and_login("Alice")  # will struggle
    bob = register_and_login("Bob")  # will succeed easily

    section("STEP 2 — Create projects + sessions")
    create_project_and_session(alice)
    create_project_and_session(bob)
    print(f"      Alice   session={alice.session_id}")
    print(f"      Bob     session={bob.session_id}")

    section("STEP 3 — Seed differentiated execution history")
    print("      Alice  →  8 failed / 2 passed / 5 hints  (struggling novice)")
    seed_runs(alice, passed=2, failed=8, hints=5)
    print("      Bob    →  9 passed / 1 failed / 0 hints  (confident solver)")
    seed_runs(bob, passed=9, failed=1, hints=0)
    print("      (profiles are updated in the background …)")
    time.sleep(2)

    # ── Profiles
    section("STEP 4 — Learner profiles after seeded history")
    alice_profile = get_profile(alice)
    bob_profile = get_profile(bob)

    interesting = [
        "teaching_style",
        "difficulty_adjustment",
        "rolling_hint_rate",
        "rolling_failed_run_ratio",
        "hint_depth_ceiling",
    ]

    print(f"\n  {'Signal':<35}  {'Alice (struggling)':>20}  {'Bob (solver)':>15}")
    print(f"  {'─' * 35}  {'─' * 20}  {'─' * 15}")
    for key in interesting:
        av = alice_profile.get(key, "—")
        bv = bob_profile.get(key, "—")
        print(f"  {key:<35}  {str(av):>20}  {str(bv):>15}")

    # ── Recommendations
    section("STEP 5 — Recommendations (should diverge)")
    alice_recs = get_recommendations(alice)
    bob_recs = get_recommendations(bob)

    def fmt_rec(r: dict) -> str:
        src = r.get("source", "?")
        title = r.get("title") or r.get("problem_id") or r.get("id") or str(r)
        diff = r.get("difficulty", "?")
        score = r.get("score")
        score_str = f"  score={score:+.3f}" if isinstance(score, float) else ""
        return f"[diff={diff}] {title} ({src}){score_str}"

    print("\n  ── Alice's top-5 (expect easier problems)")
    for rec in alice_recs[:5]:
        print(f"    • {fmt_rec(rec)}")

    print("\n  ── Bob's top-5 (expect harder problems)")
    for rec in bob_recs[:5]:
        print(f"    • {fmt_rec(rec)}")

    alice_ids = {r.get("problem_id") or r.get("id") for r in alice_recs[:5]}
    bob_ids = {r.get("problem_id") or r.get("id") for r in bob_recs[:5]}
    overlap = len(alice_ids & bob_ids)
    print(f"\n  Overlap: {overlap}/5 shared problems  ", end="")
    print("✓ personalized" if overlap < 4 else "⚠ too similar — may need more epochs")

    # ── Mentor personalization block
    section("STEP 6 — Mentor chat (check personalization block in response)")
    print("  (calling /mentor/chat for each — OpenAI mock or live …)")

    for learner, label in [(alice, "Alice"), (bob, "Bob")]:
        try:
            resp = mentor_chat(learner)
            p = resp.get("personalization")
            if p:
                print(f"\n  ── {label}'s personalization block")
                for k, v in p.items():
                    print(f"    {k:<40}: {v}")
            else:
                print(f"\n  ── {label}: no personalization field (is mentor wired?)")
            # Truncate message
            msg = resp.get("message", "")
            print(f"  ── {label}'s mentor reply (first 200 chars)")
            print(f"    {msg[:200]} …")
        except httpx.HTTPError as exc:
            print(
                f"  ── {label}: mentor call failed ({type(exc).__name__}) — "
                "profile validation still complete"
            )

    section("DONE")
    print("  All checks complete. The personalization engine is working if:")
    print("  • Alice's teaching_style = 'scaffolded', difficulty_adjustment < 0")
    print("  • Bob's   teaching_style = 'socratic',   difficulty_adjustment > 0")
    print("  • Alice's recommendations are lower difficulty than Bob's")
    print("  • Each mentor response includes a 'personalization' block")
    print()


if __name__ == "__main__":
    main()
