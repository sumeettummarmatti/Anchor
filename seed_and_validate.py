"""
seed_and_validate.py  —  Recommendation engine personalization validator

WHAT THIS DOES:
  1. Registers 3 users (novice / builder / solver) via the live API
  2. Seeds differentiated ExecutionRun + HintEvent records directly into
     the DB (bypassing Piston, which isn't needed for profile computation)
  3. Triggers PersonalizationService.update_after_session() for each user
  4. Calls GET /problems/recommended and proves that:
       a) source == bi_encoder   (model artifacts loaded)
       b) rankings differ across users   (personalization working)
       c) profiles reflect the seeded history
"""
import asyncio, json, time, sys, urllib.request, urllib.error
from uuid import uuid4
from pathlib import Path

# ── Inline HTTP helpers (stdlib only) ─────────────────────────────────────────
BASE = "http://localhost:8000"

def api(method, path, body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"__error__": e.code, "detail": body}

def register_login(email, password, name):
    api("POST", "/auth/register", {"email": email, "password": password, "display_name": name})
    resp = api("POST", "/auth/login", {"email": email, "password": password})
    if "__error__" in resp:
        raise RuntimeError(f"Login failed for {email}: {resp}")
    return resp["access_token"]

def get_me(token):
    return api("GET", "/users/me", token=token)

def get_recs(token, k=5):
    return api("GET", f"/problems/recommended?k={k}", token=token)

def get_profile(token):
    return api("GET", "/users/me/profile", token=token)

def create_project(token, name, lang="python"):
    r = api("POST", "/projects", {"name": name, "language": lang}, token=token)
    return r["id"]

def start_session(token, project_id):
    r = api("POST", "/sessions", {"project_id": project_id}, token=token)
    return r["id"]

def end_session(token, session_id):
    return api("POST", f"/sessions/{session_id}/end", token=token)

# ─────────────────────────────────────────────────────────────────────────────
async def seed_history(user_id, session_id, *, failed_runs, passed_runs, hint_count):
    """Insert synthetic execution runs + hint events directly into the DB."""
    from app.db.session import AsyncSessionLocal
    from app.models.execution import ExecutionRun
    from app.models.hint_event import HintEvent
    from app.services.personalization_service import PersonalizationService
    import uuid

    async with AsyncSessionLocal() as session:
        uid = uuid.UUID(user_id)
        sid = uuid.UUID(session_id)

        # Insert failed runs
        for _ in range(failed_runs):
            session.add(ExecutionRun(
                id=uuid.uuid4(), session_id=sid,
                code_snapshot="# stub", language="python", version="3.10",
                stdin="", stdout="", stderr="Error: runtime error",
                exit_code=1, status="error"
            ))

        # Insert passed runs
        for _ in range(passed_runs):
            session.add(ExecutionRun(
                id=uuid.uuid4(), session_id=sid,
                code_snapshot="print('ok')", language="python", version="3.10",
                stdin="", stdout="ok", stderr="",
                exit_code=0, status="completed"
            ))

        # Insert hint events
        for i in range(hint_count):
            session.add(HintEvent(
                id=uuid.uuid4(), user_id=uid, session_id=sid,
                level=(i % 3) + 1,
                prompt="Stub hint request",
                response="Stub hint response"
            ))

        await session.commit()

        # Re-compute profile from real DB records
        await PersonalizationService(session).update_after_session(uid)
        print(f"    Seeded: failed={failed_runs} passed={passed_runs} hints={hint_count} → profile updated")

# ─────────────────────────────────────────────────────────────────────────────
def show_recs(label, recs):
    print(f"\n  ── {label}")
    for r in recs:
        print(f"    [{r['score']:+.4f}] ({r['source']:13s}) {r['id']}  {r['title']}  [diff={r['difficulty']}, {r['language']}]")

def show_profile(label, p):
    print(f"\n  ── {label}")
    print(f"    teaching_style        : {p.get('teaching_style')}")
    print(f"    difficulty_adjustment : {p.get('difficulty_adjustment')}")
    print(f"    rolling_hint_rate     : {p.get('rolling_hint_rate')}")
    print(f"    rolling_failed_run_%  : {p.get('rolling_failed_run_ratio')}")
    print(f"    hint_depth_ceiling    : {p.get('hint_depth_ceiling')}")
    print(f"    sessions_completed    : {p.get('sessions_completed')}")
    print(f"    execution_runs        : {p.get('execution_runs')}")
    print(f"    hints_used            : {p.get('hints_used')}")

def analyze(label_recs):
    print("\n  ── Cross-user divergence (do different users get different recommendations?)")
    id_sets = {label: set(r['id'] for r in recs) for label, recs in label_recs.items()}
    labels = list(id_sets.keys())
    for i in range(len(labels)):
        for j in range(i+1, len(labels)):
            a, b = labels[i], labels[j]
            shared = len(id_sets[a] & id_sets[b])
            print(f"    {a:14s} ∩ {b:14s} : {shared}/5 shared  {'✓ personalized' if shared < 5 else '✗ identical'}")

    print("\n  ── Source check")
    all_recs = [r for recs in label_recs.values() for r in recs]
    sources = {r['source'] for r in all_recs}
    if 'bi_encoder' in sources:
        print("    ✓  bi_encoder ACTIVE — model artifacts loaded correctly")
    else:
        print("    ⚠  bi_encoder NOT active — using rule_fallback only")

    all_personalized = all(
        len(id_sets[a] & id_sets[b]) < 5
        for i, a in enumerate(labels)
        for b in labels[i+1:]
    )
    if all_personalized:
        print("    ✓  Rankings DIFFER across all user pairs — personalization WORKING")
    else:
        print("    ✗  Some users share identical top-5 — personalization NOT differentiating")

    return 'bi_encoder' in sources and all_personalized

# ─────────────────────────────────────────────────────────────────────────────
async def main():
    TS = int(time.time())
    divider = "━" * 56

    print(f"\n{divider}")
    print("  Recommendation Engine Validation")
    print(divider)

    # 1. Health
    print("\n[1/7] Health check")
    h = api("GET", "/health")
    print(f"      status={h['status']}  env={h['environment']}")

    # 2. Register + login
    print(f"\n[2/7] Registering 3 archetypes")
    users = {
        "novice":  (f"novice_{TS}@example.com",  "SecurePass1!", "Novice Nina"),
        "builder": (f"builder_{TS}@example.com", "SecurePass1!", "Builder Bob"),
        "solver":  (f"solver_{TS}@example.com",  "SecurePass1!", "Solver Sam"),
    }
    tokens = {}
    user_ids = {}
    for archetype, (email, pwd, name) in users.items():
        tok = register_login(email, pwd, name)
        tokens[archetype] = tok
        me = get_me(tok)
        user_ids[archetype] = me["id"]
        print(f"      {name:14s}  id={me['id']}")

    # 3. Cold recommendations
    print(f"\n[3/7] Cold-start recommendations (no history)")
    cold = {}
    for arch, tok in tokens.items():
        cold[arch] = get_recs(tok, 5)
        show_recs(arch, cold[arch])
    cold_src = cold["novice"][0]["source"] if cold["novice"] else "none"
    print(f"\n  Source (cold): {cold_src}")

    # 4. Create project + session for each user
    print(f"\n[4/7] Creating projects + sessions")
    session_ids = {}
    for arch, tok in tokens.items():
        pid = create_project(tok, f"{arch}-project-{TS}", "python")
        sid = start_session(tok, pid)
        session_ids[arch] = sid
        # end session via API so session_completed increments
        end_session(tok, sid)
        print(f"      {arch:8s}  project={pid}  session={sid}")

    # 5. Seed differentiated history & recompute profiles
    print(f"\n[5/7] Seeding differentiated execution history into DB")
    print("      (novice=many failures+hints | builder=mixed | solver=mostly passing)")

    # Novice: 8 failed, 2 passed, 6 hints → high fail ratio, high hint rate
    await seed_history(user_ids["novice"], session_ids["novice"],
                       failed_runs=8, passed_runs=2, hint_count=6)

    # Builder: 4 failed, 6 passed, 3 hints → moderate fail ratio, some hints
    await seed_history(user_ids["builder"], session_ids["builder"],
                       failed_runs=4, passed_runs=6, hint_count=3)

    # Solver: 1 failed, 9 passed, 0 hints → low fail ratio, no hints
    await seed_history(user_ids["solver"], session_ids["solver"],
                       failed_runs=1, passed_runs=9, hint_count=0)

    # 6. Show profiles
    print(f"\n[6/7] Learner profiles after seeded history")
    profiles = {arch: get_profile(tok) for arch, tok in tokens.items()}
    for arch, p in profiles.items():
        show_profile(arch, p)

    # 7. Warm recommendations + analysis
    print(f"\n[7/7] Post-interaction recommendations")
    warm = {}
    for arch, tok in tokens.items():
        warm[arch] = get_recs(tok, 5)
        show_recs(arch, warm[arch])
    warm_src = warm["novice"][0]["source"] if warm["novice"] else "none"
    print(f"\n  Source (warm): {warm_src}")

    print(f"\n{divider}")
    print("  Divergence & Personalization Analysis")
    print(divider)
    analyze(warm)

    print(f"\n{divider}")
    print("  Cold → Warm ranking shift (did history change the ranking?)")
    print(divider)
    for arch in ["novice", "builder", "solver"]:
        cold_ids = {r['id'] for r in cold[arch]}
        warm_ids = {r['id'] for r in warm[arch]}
        changed = len(cold_ids.symmetric_difference(warm_ids))
        src_change = f"{cold[arch][0]['source']} → {warm[arch][0]['source']}"
        print(f"    {arch:8s}  {changed}/5 positions changed  ({src_change})")

    print()

if __name__ == "__main__":
    asyncio.run(main())
