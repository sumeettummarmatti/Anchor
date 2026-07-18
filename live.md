# Live Tutor + Rocky — Implementation Plan

## Background & Codebase Audit

### What already exists (must reuse, not reinvent)

| Concern | Where it lives |
|---|---|
| Auth dependency | `app/core/dependencies.py` → `get_current_user` |
| DB session factory | `app/db/session.py` → `AsyncSessionLocal`, `get_db_session` |
| Learner profile (already-computed rolling averages) | `app/models/learner_profile.py` — columns: `teaching_style`, `hint_depth_ceiling`, `intervention_frequency`, `difficulty_adjustment`, `rolling_failed_run_ratio`, `rolling_hint_rate` |
| Fast-path AdaptationContext | `PersonalizationService.get_context(user_id)` → reads `LearnerProfile` directly via `LearnerProfileRepository`, does NOT re-scan raw execution history. This is the correct fast path to use on every live-nudge call. |
| Hint logging model | `app/models/hint_event.py` → `HintEvent(user_id, session_id, level, prompt, response)` |
| Hint repository | `app/repositories/hint_repository.py` → `create()`, `highest_level()` |
| Prompt context convention | `app/services/ai_service.py` → `PromptContext` dataclass; each intent's prompt is built in `app/prompt_templates/`. All new prompt logic must follow the same pattern. |
| LLM call boundary | `AIService.complete(context: PromptContext)` — this is the only function that should call the LLM. New intent "live_nudge" will be added to its builder registry. |
| Rate limit exception | `app/core/exceptions.py` → `RateLimitError` (HTTP 429) already exists |
| Redis URL | `app/core/config.py` → `settings.redis_url` |
| Existing session auth | `SessionService.get(session_id, user_id)` — already used in `mentor_service.hint()` to verify the session belongs to the user. Reuse the same pattern. |
| Frontend globals | `index.html` line 129: `token()` returns access token. Line 148: `codePayload()` returns `{language, code}`. `$('session-id').value` is the session ID. `$('code')` is the editor textarea element. No `currentSessionId` or `accessToken` global variables — these must be read via `token()` and `$('session-id').value` instead. |
| Existing hint trigger | `$('hint').addEventListener(...)` in `index.html` line 214 — "Give me a hint" in Rocky must call this same handler path, not duplicate it. |

### Key design decisions confirmed by reading the code

1. **`PersonalizationService.get_context(user_id)`** does a single SELECT on `learner_profiles` — it is the correct fast path for live-nudge. Do NOT call `update_after_session` on every nudge call.
2. **`HintEvent.level`** has no "source type" field. The spec says to add a distinguishing field for Phase 11 analytics. This requires a **new Alembic migration** to add a `source` column (nullable string, e.g. `"nudge"` vs `"requested"`).
3. **No Redis client** exists yet in the codebase — `redis_url` is in Settings but `redis` is not imported anywhere. The `live_nudge_state.py` module must initialise its own async Redis client using `redis.asyncio`.
4. **`PromptContext.intent`** is a string dispatched in `AIService.complete()` via a builders dict. Adding `"live_nudge"` means: (a) add the builder to `prompt_templates/`, (b) register it in `complete()`.
5. **`RateLimitError`** (HTTP 429) already exists in `exceptions.py`. No new exception class needed for rate limiting.
6. The frontend `request()` helper passes `authHeaders()` which reads `token()` from localStorage. Rocky's fetch must use `token()` the same way — not a global `accessToken` variable.

---

## Open Questions / Decisions

> [!IMPORTANT]
> **Database migration needed for `HintEvent.source`**: Adding a `source: str | None` column to `hint_events` is required to distinguish live nudges from requested hints for Phase 11 analytics. This is a new Alembic migration. Confirm you're OK with a schema change on the `biencoders` branch before we start.

> [!IMPORTANT]
> **Redis dependency**: `redis[asyncio]` (the `redis` Python package) needs to be added to `pyproject.toml`. It's already in the Docker Compose stack but not in Python dependencies. Confirm it's not already pinned elsewhere.

> [!NOTE]
> **No `requestProgressiveHint()` global exists yet**: The spec says Rocky's "Give me a hint" button must call `requestProgressiveHint()`. That function doesn't exist yet as a standalone callable — the hint logic is currently inline in a click handler. The plan will extract it into a named function so Rocky can call it.

> [!NOTE]
> **`currentProblemId` doesn't exist on the frontend**: The spec references `currentProblemId` in the live-nudge payload. The current demo frontend has no problem concept. The plan sends `problem_id: null` (schema makes it optional) and the spec confirms `problem_id` is optional in `LiveNudgeRequest`. This is fine for the demo.

---

## Proposed Changes

---

### Part A — Backend

---

#### [NEW] `app/schemas/live_nudge.py`

Three Pydantic models:

```python
class LiveNudgeRequest(BaseModel):
    session_id: UUID
    problem_id: UUID | None = None
    code: str = Field(min_length=0, max_length=200_000)
    language: str = Field(min_length=1, max_length=64)
    client_detected_signal: str | None = Field(default=None, max_length=128)
    # "idle_800ms", "empty_file", "test_run_passed" — trigger reason only

class NudgeType(StrEnum):
    orientation = "orientation"
    encourage   = "encourage"
    scaffold    = "scaffold"
    pinpoint    = "pinpoint"
    celebrate   = "celebrate"

class LiveNudgeResponse(BaseModel):
    nudge: str          # ≤ 2 sentences, enforced at prompt level
    nudge_type: NudgeType
    stage: str          # LLM-inferred generic stage string
    should_display: bool

class LiveNudgeFeedback(BaseModel):
    session_id: UUID
    helpful: bool
```

**Verify**: `python -c "from app.schemas.live_nudge import LiveNudgeRequest, LiveNudgeResponse, LiveNudgeFeedback; print('ok')`

---

#### [NEW] `app/core/live_nudge_state.py`

Redis-backed suppression state. Uses `redis.asyncio`. Key design:

- All state stored under key pattern `live_nudge:{session_id}` as a Redis hash with fields: `last_stage`, `last_nudge_ts`, `dismissed_until`, `nudge_count`.
- **`DISMISSED_LOCK_MINUTES = 10`** — configurable constant at module top.
- **`POST_SOLVE_STAGE = "solved"`** — unconditional post-solve cooldown.
- **`get_redis()`** must be a plain importable module-level function (not a class attribute) so `unittest.mock.patch("app.core.live_nudge_state.get_redis", ...)` works cleanly in tests. Verify this patch point works after Step 3 lands, before writing suppression tests on top of it.

> [!IMPORTANT]
> **Suppression is split into two functions with distinct responsibilities.** A single `should_suppress(session_id, current_stage)` that passes the stored `last_stage` back as its own argument is tautological — the same-stage check always fires from the second call onward, silencing Live Tutor permanently regardless of real learner progress.

```python
async def get_redis() -> redis.asyncio.Redis:
    # Returns a module-level singleton connection pool backed by settings.redis_url
    # Must be a plain importable function for test patching.

async def get_nudge_state(session_id: UUID) -> dict:
    """Read the full Redis hash for this session. Returns empty dict if not set."""

async def should_suppress_pretrigger(session_id: UUID) -> bool:
    """
    Call BEFORE the LLM runs. Only checks time-based locks:
    - dismissed_until is set and now() < dismissed_until
    - last_stage == POST_SOLVE_STAGE (post-solve cooldown)
    MUST NEVER compare stages here — the true current stage is not known
    until the LLM classifies it. Using the stored stage as the 'guess'
    would make the same-stage lock always fire from the second nudge onward.
    """

async def should_suppress_posttrigger(session_id: UUID, actual_stage: str) -> bool:
    """
    Call AFTER the LLM returns its classified stage.
    Only this function does the same-stage-lock comparison,
    against the REAL new stage, not a stored guess.
    """
    state = await get_nudge_state(session_id)
    return state.get("last_stage") == actual_stage

async def record_nudge(session_id: UUID, stage: str) -> None:
    """Update last_stage, last_nudge_ts, increment nudge_count after a successful nudge."""

async def set_dismissed(session_id: UUID) -> None:
    """Set dismissed_until = now() + DISMISSED_LOCK_MINUTES. Called when helpful=False."""

async def check_rate_limit(user_id: UUID, session_id: UUID, *, limit: int = 10, window_seconds: int = 60) -> None:
    """
    Rate limiter for live-nudge. Key: live_nudge_rl:{user_id}:{session_id}
    Uses Redis INCR + EXPIRE. Raises RateLimitError if limit exceeded.
    Note: INCR+EXPIRE is a FIXED window, not a true sliding window — a burst
    at the window boundary can let through ~2x the intended rate. Acceptable
    for demo; do not rely on the exact number as a hard guarantee in production.
    Flagged as pulled-forward from Phase 14.
    """
```

**Verify after Step 3**: Manually confirm `unittest.mock.patch("app.core.live_nudge_state.get_redis", ...)` resolves correctly before writing suppression tests. Run:
```bash
python -c "from app.core import live_nudge_state; print(live_nudge_state.get_redis)"
```
Expected: a function object (not a bound method or property).

---

#### [NEW] `app/prompt_templates/live_nudge.py`

Follows the exact `build(context: PromptContext) -> tuple[str, str]` convention:

```python
def build(context: PromptContext) -> tuple[str, str]:
    # context.intent == "live_nudge"
    # context.adaptation is AdaptationContext
    # context.learner_message contains client_detected_signal (or "idle pause")
    # context.code is the current editor content
    # context.language is the language
    system = _build_system(context.adaptation)
    user   = _build_user(context)
    return system, user

def _build_system(adaptation: AdaptationContext | None) -> str:
    # Directive constraints:
    # - Respond in AT MOST 2 sentences. Do not exceed this limit.
    # - Do not reveal the answer directly. Ask a question instead.
    # - Never invent code for the learner.
    # Adaptation injection:
    # - If hint_depth_ceiling <= 2: "Be more directive and explicit — this learner benefits from scaffolding."
    # - If teaching_style == "scaffolded": "Prefer concrete directional nudges over open-ended questions."
    # - If teaching_style == "socratic": "Prefer open-ended questions over direct suggestions."
    # - Infer the learner's stage generically from the code (blank=orientation, attempt=exploring, near-correct=pinpoint, tests-pass=solved).

def _build_user(context: PromptContext) -> str:
    # Injects: language, code snippet (truncated to 3000 chars), client_detected_signal as a soft hint.
    # Response format instruction: JSON object with keys: nudge, nudge_type, stage.
```

> [!IMPORTANT]
> The LLM response must be **structured JSON** (`nudge`, `nudge_type`, `stage`). `AIService.live_nudge()` will parse this JSON from the raw completion string. Add a `response_format` instruction in the system prompt. If JSON parsing fails, log and return `should_display=False`.

**Verify**: Unit test — pass a dummy `PromptContext` and assert the returned `system` string contains the 2-sentence constraint and at least one adaptation signal.

---

#### [MODIFY] `app/services/ai_service.py`

Two changes only — do NOT touch any existing methods:

1. **Register the new builder in `complete()`**:
```python
builders = {
    "chat":        mentor_chat.build,
    "hint":        mentor_hint.build,
    "explain_error": explain_error.build,
    "live_nudge":  live_nudge.build,   # ← add this line
}
```

2. **Add `live_nudge()` method** after the existing `complete()` method:
```python
async def live_nudge(
    self,
    request: "LiveNudgeRequest",
    adaptation: "AdaptationContext",
    *,
    session: AsyncSession,
    user_id: UUID,
) -> "LiveNudgeResponse":
    from app.core.live_nudge_state import (
        check_rate_limit,
        record_nudge,
        should_suppress_posttrigger,
        should_suppress_pretrigger,
    )
    from app.repositories.hint_repository import HintRepository
    from app.schemas.live_nudge import LiveNudgeResponse, NudgeType
    import json

    # Step 1 — Rate limit check (raises RateLimitError → HTTP 429 if exceeded)
    await check_rate_limit(user_id, request.session_id)

    # Step 2 — Pre-LLM suppression: time-based locks only (dismissed, post-solve).
    # Do NOT pass or compare last_stage here — stage is unknown until the LLM runs.
    if await should_suppress_pretrigger(request.session_id):
        return LiveNudgeResponse(
            nudge="", nudge_type=NudgeType.encourage, stage="", should_display=False
        )

    # Step 3 — Build PromptContext and call LLM
    context = PromptContext(
        intent="live_nudge",
        language=request.language,
        code=request.code,
        learner_message=request.client_detected_signal or "idle pause",
        adaptation=adaptation,
    )
    try:
        raw_text, _model = await self.complete(context)
        parsed = json.loads(raw_text)
        nudge = parsed.get("nudge", "")
        nudge_type = NudgeType(parsed.get("nudge_type", "encourage"))
        stage = parsed.get("stage", "unknown")
    except json.JSONDecodeError:
        # Distinct log so "model returned garbage" is distinguishable from
        # "model chose not to speak" (both return should_display=False).
        logger.warning("live_nudge_json_parse_failed",
                       user_id=str(user_id), session_id=str(request.session_id))
        return LiveNudgeResponse(
            nudge="", nudge_type=NudgeType.encourage, stage="unknown", should_display=False
        )
    except Exception:
        return LiveNudgeResponse(
            nudge="", nudge_type=NudgeType.encourage, stage="unknown", should_display=False
        )

    # Step 4 — Post-LLM same-stage lock: NOW we have the actual classified stage.
    # This is the only place the same-stage comparison is valid.
    if await should_suppress_posttrigger(request.session_id, stage):
        return LiveNudgeResponse(
            nudge="", nudge_type=nudge_type, stage=stage, should_display=False
        )

    # Step 5 — Update Redis state and log HintEvent
    await record_nudge(request.session_id, stage)
    repo = HintRepository(session)
    await repo.create(HintEvent(
        user_id=user_id,
        session_id=request.session_id,
        level=0,        # level=0 distinguishes live nudges from progressive hints 1-5
        prompt=request.code[:500],
        response=nudge,
        source="nudge", # new column (Alembic migration Step 2)
    ))
    return LiveNudgeResponse(nudge=nudge, nudge_type=nudge_type, stage=stage, should_display=True)
```

**Verify**: `uv run pytest tests/test_live_nudge.py -xvs` (suppressed path asserts AI client not called)

> [!NOTE]
> **Three smaller fixes incorporated above (not blockers but now in-plan):**
> 1. **Silent JSON-parse failures now log distinctly**: `logger.warning("live_nudge_json_parse_failed", ...)` is emitted before returning `should_display=False` when JSON parsing fails. During a demo, "model returned garbage" vs "model chose not to speak" is now distinguishable in server logs.
> 2. **Rate limiter is fixed-window, not true sliding-window**: The INCR+EXPIRE pattern resets at a fixed boundary. A burst at the window edge can pass ~2× the intended rate. Acceptable for demo; noted in docstring and log.md entry.
> 3. **`get_redis()` patch point**: Must be a plain importable function at module level, not a class attribute. Explicitly verified after Step 3 lands before tests are written.

---

#### [NEW] Alembic migration — add `source` to `hint_events`

```bash
uv run alembic revision --autogenerate -m "add_source_to_hint_events"
```

Migration will add:
```python
op.add_column('hint_events', sa.Column('source', sa.String(32), nullable=True))
```

Also update `HintEvent` model:
```python
source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

**Verify**: `uv run alembic upgrade head` completes without error. `\d hint_events` in psql shows the `source` column.

---

#### [MODIFY] `app/api/routers/mentor.py`

Add two new routes at the bottom of the file:

```python
@router.post("/live-nudge", response_model=LiveNudgeResponse)
async def live_nudge(
    payload: LiveNudgeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LiveNudgeResponse:
    # 1. Fast-path personalization — reads pre-computed profile, no history scan
    try:
        adaptation = await PersonalizationService(session).get_context(current_user.id)
    except Exception:
        logger.warning("live_nudge_profile_fallback", user_id=str(current_user.id))
        adaptation = AdaptationContext(   # safe defaults
            hint_depth_ceiling=3,
            teaching_style="socratic",
            difficulty_adjustment=0.0,
            intervention_frequency=0.35,
            rolling_hint_rate=0.0,
            rolling_failed_run_ratio=0.0,
            rolling_avg_solve_time_seconds=0.0,
        )
    # 2. Session ownership check (reuse existing pattern from mentor_service.hint())
    await SessionService(session).get(payload.session_id, current_user.id)
    # 3. Delegate to AIService
    return await AIService(settings).live_nudge(
        payload, adaptation, session=session, user_id=current_user.id
    )


@router.post("/live-nudge/feedback", status_code=204)
async def live_nudge_feedback(
    payload: LiveNudgeFeedback,
    current_user: User = Depends(get_current_user),
) -> None:
    if not payload.helpful:
        from app.core.live_nudge_state import set_dismissed
        await set_dismissed(payload.session_id)
```

**Verify**:
```bash
curl -s -X POST http://127.0.0.1:8000/mentor/live-nudge \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<id>","code":"def solve(): pass","language":"python"}'
```
Expected: `{"nudge":"...","nudge_type":"...","stage":"...","should_display":true|false}`

---

#### [MODIFY] `app/main.py`

Register router (no changes to existing includes):
```python
# Already includes mentor_router — live-nudge routes are added to the same router,
# so NO change to main.py is needed.
```

---

### Part B — Frontend (`app/static/index.html`)

All changes are to the single `index.html` file. Done in three injections:

#### B1 — Rocky HTML (inject just before `</main>`)
Exactly as specified. No changes to spec HTML.

#### B2 — Rocky CSS (inject inside `<style>` block, after existing styles)
Exactly as specified. Rocky bubble `button` rule must NOT conflict with existing `button` rule — scope it under `.rocky-bubble button` (already done in spec CSS).

#### B3 — Rocky JS + Live Tutor wiring (inject inside `<script>` block)

**Variable name mapping** (from audit of index.html):

| Spec variable | Actual name in index.html |
|---|---|
| `accessToken` | `token()` — a function call, not a global variable |
| `currentSessionId` | `$('session-id').value` |
| `currentProblemId` | `null` — not in the demo, send as null |
| `currentLanguage` | `$('language').value` |
| `editor` | `$('code')` — the textarea element |

**`requestProgressiveHint()`** must be extracted as a standalone function from the existing `$('hint').addEventListener` handler so Rocky can call it. The existing handler will call this function:

```javascript
async function requestProgressiveHint() {
    // Extract existing hint logic here (lines 214–222 of current index.html)
}
$('hint').addEventListener('click', async () => {
    try { await requestProgressiveHint(); } catch (error) { showError(error); }
});
```

**`estimateTypingSpeedWpm()`** implementation:
```javascript
const _keystrokeTimes = [];
document.addEventListener('keydown', () => {
    const now = Date.now();
    _keystrokeTimes.push(now);
    // Keep only last 10 seconds
    while (_keystrokeTimes.length > 0 && now - _keystrokeTimes[0] > 10000)
        _keystrokeTimes.shift();
});
function estimateTypingSpeedWpm() {
    if (_keystrokeTimes.length < 2) return 0;
    const span = (_keystrokeTimes[_keystrokeTimes.length - 1] - _keystrokeTimes[0]) / 1000;
    const kps = (_keystrokeTimes.length - 1) / span;
    return kps * 12; // rough chars-to-WPM (5 chars/word × 60s/min ÷ 25 keystrokes/word ≈ 12)
}
```

**Live Tutor toggle**: Add a toggle button in the session card (section 2):
```html
<button type="button" id="live-tutor-toggle" class="ghost">🐾 Live Tutor: OFF</button>
```
Wire it:
```javascript
$('live-tutor-toggle').addEventListener('click', () => {
    liveModeActive = !liveModeActive;
    $('live-tutor-toggle').textContent = `🐾 Live Tutor: ${liveModeActive ? 'ON' : 'OFF'}`;
    onLiveToggle(liveModeActive);
});
```

**Verify**: Open `http://127.0.0.1:8000/demo/`, log in, create a session, click "Live Tutor: OFF" to toggle it on. Type in the code editor, pause 800ms — Rocky should bob then show a bubble.

---

### Part C — Tests (`tests/test_live_nudge.py`)

#### Test structure overview

```
test_live_nudge.py
│
├── Unit — suppression logic (no DB, uses fakeredis or patched get_redis)
│   ├── test_should_suppress_same_stage
│   ├── test_should_suppress_dismissed_lock
│   ├── test_should_suppress_post_solve
│   └── test_should_not_suppress_different_stage_no_lock
│
├── Integration — POST /mentor/live-nudge (httpx test client, mocked AIService)
│   ├── test_live_nudge_happy_path_returns_nudge
│   ├── test_live_nudge_suppressed_returns_should_display_false
│   │     └── asserts mock LLM client was NOT called
│   ├── test_live_nudge_rate_limit_triggers
│   └── test_live_nudge_personalization_reaches_prompt
│         └── two users, different hint_depth_ceiling,
│             assert AdaptationContext.hint_depth_ceiling differs in prompt
│
└── Integration — POST /mentor/live-nudge/feedback
    ├── test_feedback_not_helpful_sets_dismissed_lock
    └── test_feedback_then_nudge_is_suppressed
```

#### Key test patterns

**Suppression unit tests** — patch `get_redis()` to return a `fakeredis.aioredis.FakeRedis()` instance. All suppression tests are pure function tests against the state stored in fake Redis.

**Mocked LLM assertion** — use `AsyncMock` to patch `AIService.complete`. Assert `complete.assert_not_called()` on the suppressed path.

**Rate limit test** — call the endpoint 11 times rapidly in a loop via the test client. Assert the 11th returns HTTP 429.

**Personalization test** — create two users, set their `LearnerProfile.hint_depth_ceiling` to 2 and 5 respectively. Call `live_nudge` for each with identical code+problem. Capture the `PromptContext` passed to `AIService.complete` via a mock. Assert `context.adaptation.hint_depth_ceiling` differs between the two calls.

**Verify**: `uv run pytest tests/test_live_nudge.py -v`

---

### Part D — `log.md` append

Append a new dated entry at the top of `log.md` with the four cross-reference notes specified:
1. Rate limiting pulled forward from Phase 14.
2. Live-nudge suppression overlaps with Phase 8 `stuck_detection_service`.
3. Stage classification is LLM-inferred generically, not a per-problem table.
4. Rocky's state model is inspired by OpenPets (Swift app by alterhq).

---

## Dependency Addition

Add to `pyproject.toml` dependencies:
```
redis[asyncio]>=5.0
fakeredis[aioredis]>=2.0   # dev/test group only
```

Install:
```bash
uv add redis[asyncio]
uv add --group dev "fakeredis[aioredis]"
```

**Verify**: `python -c "import redis.asyncio; print('ok')`

---

## Execution Order (Strict)

Each step is independently verifiable before proceeding.

```
[ ] Step 0 — Dependencies
      uv add redis[asyncio] && uv add --group dev "fakeredis[aioredis]"
      Verify: python -c "import redis.asyncio; print('ok')"

[ ] Step 1 — app/schemas/live_nudge.py  [NEW]
      Verify: python -c "from app.schemas.live_nudge import LiveNudgeRequest; print('ok')"

[ ] Step 2 — Alembic migration: add HintEvent.source column
      uv run alembic revision --autogenerate -m "add_source_to_hint_events"
      uv run alembic upgrade head
      Verify: psql or curl GET /users/me/profile (server starts without error)

[ ] Step 3 — app/core/live_nudge_state.py  [NEW]
      Verify: python -c "from app.core.live_nudge_state import should_suppress; print('ok')"

[ ] Step 4 — app/prompt_templates/live_nudge.py  [NEW]
      Verify: python -c "from app.prompt_templates import live_nudge; print('ok')"

[ ] Step 5 — app/prompt_templates/__init__.py  [MODIFY]
      Add: from app.prompt_templates import live_nudge
      Add to __all__: "live_nudge"

[ ] Step 6 — app/services/ai_service.py  [MODIFY]
      Register "live_nudge" in builders dict; add live_nudge() method.
      Verify: uv run ruff check app/services/ai_service.py

[ ] Step 7 — app/api/routers/mentor.py  [MODIFY]
      Add /live-nudge and /live-nudge/feedback routes.
      Restart server and verify:
        curl -s http://127.0.0.1:8000/docs | grep "live-nudge"

[ ] Step 8 — tests/test_live_nudge.py  [NEW]
      Verify: uv run pytest tests/test_live_nudge.py -v

[ ] Step 9 — app/static/index.html  [MODIFY]
      Inject Rocky HTML, CSS, JS, toggle button, and live-tutor wiring.
      Verify: Manual walkthrough (see checklist below)

[ ] Step 10 — log.md  [MODIFY]
      Append the four cross-reference log entries.
```

---

## Manual Verification Checklist (Step 9)

Run after Step 9 — walk through all five checks before declaring done:

- [ ] Toggle Live Tutor on (`🐾 Live Tutor: OFF` → `ON`), type in editor, pause — Rocky bobs, then shows a bubble with 3 buttons.
- [ ] Drag Rocky to a different corner — confirm it stays there through a full nudge cycle.
- [ ] Trigger two nudges in quick succession (type → pause, type again immediately → pause) — confirm the bubble **updates in place** rather than stacking a second one.
- [ ] Kill the backend server while Rocky is showing "running" — confirm Rocky shakes and resets to idle within ~2s, not frozen.
- [ ] Click "Give me a hint" from a live nudge bubble — confirm the existing hint level counter advances and `$('hint-output')` updates, NOT a separate hint flow.

---

## Flags for Broader Refactor (Out of Scope — Do Not Inline)

1. **Phase 14 middleware**: The `check_rate_limit()` function in `live_nudge_state.py` is a minimal, self-contained limiter. When Phase 14's general rate-limiting middleware lands, this should be consolidated. Log entry covers this.
2. **Phase 8 stuck detection**: `stuck_detection_service.py` currently exists as a stub (44 bytes). Live nudge maintains its own lightweight suppression. When Phase 8 is built, evaluate whether live nudge should consume `stuck_score` directly. Log entry covers this.
3. **JSON response parsing fragility**: The LLM is instructed to return JSON but may not always comply. A more robust approach (function calling / structured outputs) would be added in a future hardening pass — out of scope here.
