# AI Coding Mentor Platform — Backend Implementation Plan

## Overview

A production-quality FastAPI backend for an adaptive AI coding mentor platform. The backend is the *entire product* — testable via Swagger UI at `/docs`, `curl`, or `pytest`. No frontend in scope.

> [!IMPORTANT]
> The existing `codex-hackathon` repo is a Vite/JS project. The new backend will live at **`/Users/sumeet/Desktop/codex-hackathon/backend/`** as a standalone Python package inside the monorepo. This keeps everything in one Git repo while keeping the Python and JS concerns separated by directory.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Project root**: Should the backend be a sibling directory inside `codex-hackathon/` (e.g. `codex-hackathon/backend/`) or an entirely separate repo/folder? The plan assumes `codex-hackathon/backend/` unless you specify otherwise.

> [!IMPORTANT]
> **Q2 — Package manager**: Use `uv` (fast, modern) or classic `pip` + `venv`? Recommend `uv` — it resolves and locks in seconds and is increasingly the standard. `pyproject.toml` will be the single source of truth either way.

> [!IMPORTANT]
> **Q3 — OAuth credentials**: Google/GitHub OAuth requires real client IDs/secrets. For Phase 2 we'll wire the flow and test with mocks. Do you already have OAuth apps registered, or should we document the setup steps and leave it as an env-var stub?

> [!IMPORTANT]
> **Q4 — OpenAI model**: Default to `gpt-4o` (best reasoning, reasonable cost)? Or `gpt-4o-mini` for dev/test budget? Recommend using `gpt-4o-mini` as the default with the model name as a config field so you can override per-environment.

---

## Proposed Directory Structure

```
codex-hackathon/
└── backend/
    ├── pyproject.toml            # deps, build config, pytest config
    ├── .env.example              # all required env vars documented
    ├── .env                      # gitignored
    ├── alembic.ini               # alembic config
    ├── docker-compose.yml        # postgres + redis + piston + app
    ├── Dockerfile                # backend app image
    ├── log.md                    # dev journal
    │
    ├── alembic/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/             # migration files go here
    │
    ├── app/
    │   ├── main.py               # FastAPI app factory, lifespan, exception handlers
    │   │
    │   ├── core/
    │   │   ├── config.py         # pydantic-settings Settings class
    │   │   ├── security.py       # JWT create/verify, password hash
    │   │   ├── dependencies.py   # get_current_user, get_db, get_redis
    │   │   ├── exceptions.py     # custom exception classes
    │   │   └── logging.py        # structlog / JSON logger setup
    │   │
    │   ├── db/
    │   │   ├── base.py           # SQLAlchemy declarative base
    │   │   └── session.py        # async engine + session factory
    │   │
    │   ├── models/               # SQLAlchemy ORM models (one file per aggregate)
    │   │   ├── user.py
    │   │   ├── refresh_token.py
    │   │   ├── project.py
    │   │   ├── session.py
    │   │   ├── execution_run.py
    │   │   ├── learner_profile.py
    │   │   ├── hint_event.py
    │   │   ├── stuck_score.py
    │   │   ├── interview.py
    │   │   ├── problem.py
    │   │   ├── analytics.py
    │   │   ├── gamification.py
    │   │   └── streak.py
    │   │
    │   ├── schemas/              # Pydantic v2 request/response models
    │   │   ├── auth.py
    │   │   ├── user.py
    │   │   ├── project.py
    │   │   ├── session.py
    │   │   ├── execution.py
    │   │   ├── static_analysis.py
    │   │   ├── mentor.py
    │   │   ├── interview.py
    │   │   ├── visualization.py
    │   │   ├── analytics.py
    │   │   ├── gamification.py
    │   │   └── problem.py
    │   │
    │   ├── repositories/         # DB access layer (one file per aggregate)
    │   │   ├── user_repo.py
    │   │   ├── project_repo.py
    │   │   ├── session_repo.py
    │   │   ├── execution_repo.py
    │   │   ├── learner_profile_repo.py
    │   │   ├── hint_repo.py
    │   │   ├── stuck_repo.py
    │   │   ├── interview_repo.py
    │   │   ├── problem_repo.py
    │   │   ├── analytics_repo.py
    │   │   └── gamification_repo.py
    │   │
    │   ├── services/             # Business logic (never calls DB directly)
    │   │   ├── auth_service.py
    │   │   ├── execution_service.py
    │   │   ├── static_analysis_service.py
    │   │   ├── ai_service.py
    │   │   ├── personalization_service.py
    │   │   ├── stuck_detection_service.py
    │   │   ├── interview_service.py
    │   │   ├── visualization_service.py
    │   │   ├── analytics_service.py
    │   │   ├── gamification_service.py
    │   │   └── problem_service.py
    │   │
    │   ├── prompt_templates/     # All LLM prompt construction lives here
    │   │   ├── mentor_chat.py
    │   │   ├── mentor_hint.py
    │   │   ├── explain_error.py
    │   │   ├── interview.py
    │   │   └── instructor_summary.py
    │   │
    │   └── routers/              # HTTP layer (thin, delegates to services)
    │       ├── auth.py
    │       ├── users.py
    │       ├── projects.py
    │       ├── sessions.py
    │       ├── execution.py
    │       ├── static_analysis.py
    │       ├── mentor.py
    │       ├── interview.py
    │       ├── visualization.py
    │       ├── analytics.py
    │       ├── gamification.py
    │       ├── problems.py
    │       └── instructor.py
    │
    └── tests/
        ├── conftest.py           # fixtures: test app, async client, test DB
        ├── test_health.py
        ├── test_auth.py
        ├── test_projects.py
        ├── test_sessions.py
        ├── test_execution.py
        ├── test_static_analysis.py
        ├── test_mentor.py
        ├── test_interview.py
        ├── test_visualization.py
        ├── test_analytics.py
        ├── test_gamification.py
        └── test_problems.py
```

---

## Phased Implementation Plan

### Phase 1 — Foundation
**Goal**: A running FastAPI app with DB connectivity, Redis, Alembic, and health check. Docker Compose includes Postgres, Redis, and self-hosted Piston.

**What gets built:**
- `pyproject.toml` with all dependencies declared upfront
- `.env.example` with every variable documented
- `docker-compose.yml` — services: `app`, `postgres`, `redis`, `piston`
- `Dockerfile` for the app
- `app/core/config.py` — `Settings` via `pydantic-settings`
- `app/core/exceptions.py` — custom exception hierarchy
- `app/core/logging.py` — structlog JSON setup
- `app/db/base.py` + `app/db/session.py` — async SQLAlchemy engine
- `app/main.py` — app factory, lifespan (DB + Redis connect/disconnect), exception handlers, `/health` route
- `alembic/` — scaffolded, `env.py` wired to async engine
- `tests/conftest.py` — async test client, in-memory SQLite for unit tests
- `tests/test_health.py`
- Initial `log.md` entry

**Testable at end of phase:**
```bash
docker-compose up -d
curl http://localhost:8000/health          # → {"status": "ok", "db": "ok", "redis": "ok"}
curl http://localhost:8000/docs            # Swagger UI
pytest tests/test_health.py               # all green
```

**Key decisions this phase surfaces:**
- Python package manager (`uv` vs `pip`)
- Exact Piston Docker image tag and runtime pre-installation strategy
- Whether to use SQLite for unit test fixtures or a test-schema in Postgres

---

### Phase 2 — Auth & Users
**Goal**: Full JWT auth with email/password + OAuth skeleton. Protected endpoints work.

**What gets built:**
- `app/models/user.py`, `app/models/refresh_token.py`
- Alembic migration: `users` + `refresh_tokens` tables
- `app/core/security.py` — bcrypt hashing, JWT access/refresh creation + verification
- `app/core/dependencies.py` — `get_current_user` FastAPI dependency
- `app/repositories/user_repo.py`
- `app/services/auth_service.py`
- `app/schemas/auth.py`, `app/schemas/user.py`
- `app/routers/auth.py` — `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`
- `app/routers/auth.py` — `GET /auth/oauth/{provider}/login`, `/auth/oauth/{provider}/callback` (Google + GitHub, via `authlib`)
- `app/routers/users.py` — `GET /users/me`, `PATCH /users/me`
- `tests/test_auth.py`

**Testable at end of phase:**
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"Secret123!","display_name":"Alice"}'

# Login → get access_token + refresh_token
# Use access_token to hit GET /users/me
# Refresh token rotation
# Logout revokes refresh token
```

---

### Phase 3 — Projects, Files & Sessions
**Goal**: Multi-file project workspace + session lifecycle with event ingestion.

**What gets built:**
- `app/models/project.py`, `app/models/session.py` (+ `File` model)
- Alembic migration
- Repos + services + schemas + routers for `projects`, `sessions`
- `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`
- `POST /projects/{id}/files`, `GET /projects/{id}/files`, `PUT /projects/{id}/files/{path}`, `DELETE /projects/{id}/files/{path}`
- `POST /sessions` (start), `PATCH /sessions/{id}` (end), `POST /sessions/{id}/events` (editor events batch)
- Defensive rate limiting on `/sessions/{id}/events` (in-memory for now, Redis in Phase 14)
- `tests/test_projects.py`, `tests/test_sessions.py`

---

### Phase 4 — Execution Service (Piston)
**Goal**: Code runs against self-hosted Piston. Every run persisted. Submit mode grades tests.

**What gets built:**
- `app/models/execution_run.py`
- Alembic migration
- `app/services/execution_service.py` — wraps Piston `/api/v2/execute`, enforces timeout ceilings, normalizes response into `ExecutionResult` schema
- `app/repositories/execution_repo.py`
- `app/schemas/execution.py`
- `app/routers/execution.py` — `POST /execution/run`, `POST /execution/submit`
- `POST /execution/runtimes` — proxy to Piston's runtime list (useful for Swagger testing)
- `tests/test_execution.py` (Piston mocked in unit tests; live test behind `RUN_LIVE_INTEGRATION_TESTS=1`)

**Testable:**
```bash
curl -X POST http://localhost:8000/execution/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"language":"python","code":"print(\"hello world\")","stdin":""}'
# → {"stdout":"hello world\n","stderr":"","exit_code":0,"execution_time_ms":120}
```

---

### Phase 5 — Static Analysis Service
**Goal**: Per-language linting integrated into execution flow and exposed standalone.

**What gets built:**
- `app/services/static_analysis_service.py` — subprocess dispatcher per language, strict timeout, structured output
  - Python: `ruff check --output-format=json`
  - JavaScript: `eslint --format=json` (if eslint installed)
  - C/C++: `clang-tidy` stub
  - Java: `checkstyle` stub
- `app/schemas/static_analysis.py` — `Diagnostic(line, col, severity, code, message)`
- `app/routers/static_analysis.py` — `POST /static-analysis/run`
- Wire into `execution_service.py`: static analysis runs first, result stored in `ExecutionRun.static_analysis_result`
- `tests/test_static_analysis.py`

---

### Phase 6 — AI Mentor Service
**Goal**: Socratic mentor chat, graded hint system, error explanation — all grounded in static analysis output and learner context.

**What gets built:**
- `app/services/ai_service.py` — wraps `openai.AsyncOpenAI`, single point of LLM calls, retry + timeout
- `app/prompt_templates/mentor_chat.py` — assembles system + user prompt from: static analysis diagnostics, learner profile (stubbed in this phase), session hint history, current code
- `app/prompt_templates/mentor_hint.py` — level-aware prompt; level 5 returns full solution only if unlocked
- `app/prompt_templates/explain_error.py`
- `app/models/hint_event.py` + Alembic migration
- `app/repositories/hint_repo.py`
- `app/services/` mentor logic (hint progression enforcement: cannot skip to level 5)
- `app/routers/mentor.py` — `POST /mentor/chat`, `POST /mentor/hint`, `POST /mentor/explain-error`
- `tests/test_mentor.py` (AIService mocked)

**Key design rule enforced**: Every `AIService` call receives a `PromptContext` dataclass — never raw f-strings from outside `prompt_templates/`.

---

### Phase 7 — Learner Profile & Personalization
**Goal**: Per-user adaptive profile that evolves over time and modifies mentor behavior.

**What gets built:**
- `app/models/learner_profile.py` + Alembic migration
- `app/repositories/learner_profile_repo.py`
- `app/services/personalization_service.py` — reads profile + history, produces `AdaptationContext` (hint depth ceiling, teaching style, difficulty adj, intervention freq)
- Auto-create `LearnerProfile` on first session start
- Background task: update profile after session ends (non-blocking via `BackgroundTasks`)
- Wire `AdaptationContext` into all mentor prompt templates
- `GET /users/me/profile` — read learner profile

---

### Phase 8 — Stuck Detection Service
**Goal**: Real-time stuck score computed from observable signals; proactive mentor triggers.

**What gets built:**
- `app/models/stuck_score.py` + Alembic migration
- `app/services/stuck_detection_service.py` — pure function `compute_stuck_score(session_events, execution_runs, hint_events) → StuckScore`
  - Signals: repeated edits without progress, consecutive failures, inactivity gap, high hint rate, oscillation pattern
- `app/repositories/stuck_repo.py`
- Hook into: post-`ExecutionRun` save, post-event-batch ingest (via `BackgroundTasks`)
- Threshold crossing → sets a flag on the session row
- `GET /sessions/{id}/stuck-score` endpoint
- `mentor/chat` checks stuck flag → prepends proactive intervention to response

---

### Phase 9 — Interview Mode
**Goal**: Post-solve technical interview driven by the learner's actual submitted code.

**What gets built:**
- `app/models/interview.py` + Alembic migration
- `app/repositories/interview_repo.py`
- `app/prompt_templates/interview.py` — question generation prompt seeded with submitted code + problem description
- `app/services/interview_service.py` — state machine: pending → in_progress → completed; question sequencing; AI answer evaluation
- `app/routers/interview.py` — `POST /interview/start`, `POST /interview/{id}/answer`, `GET /interview/{id}`
- `tests/test_interview.py`

---

### Phase 10 — Visualization Service
**Goal**: Language-agnostic execution trace JSON for a future visualizer frontend.

**What gets built:**
- `app/services/visualization_service.py` — Python tracer via `sys.settrace` in an isolated subprocess; captures per-line: local variables, call stack frames, stdout so far
- Output schema: `TraceResult(steps: List[TraceStep(line, variables, call_stack, stdout_so_far)])`
- Language stubs for JS, Java, C++ documented in code comments
- `app/routers/visualization.py` — `POST /visualization/trace`
- `tests/test_visualization.py`

---

### Phase 11 — Analytics Service
**Goal**: Append-only event log + aggregated summaries for learners.

**What gets built:**
- `app/models/analytics.py` (AnalyticsEvent) + Alembic migration
- `app/repositories/analytics_repo.py` — insert event, aggregation queries (by time window, by event type)
- `app/services/analytics_service.py`
- Wire event appends throughout: session start/end, execution run, hint usage, interview completion
- `app/routers/analytics.py` — `GET /analytics/me/summary`, `GET /analytics/me/weekly`, `GET /analytics/me/monthly`
- `tests/test_analytics.py`

---

### Phase 12 — Gamification
**Goal**: XP ledger, achievement system, streaks — rewarding learning behaviors.

**What gets built:**
- `app/models/gamification.py` — `XPLedger`, `Achievement` (definitions), `UserAchievement`, `Streak`
- Alembic migration
- `app/repositories/gamification_repo.py`
- Achievement rules as `ACHIEVEMENT_DEFINITIONS` list in a config module — each rule is `{id, name, condition_fn}` where `condition_fn` is a pure function of user analytics snapshot; no hardcoded if/else chains
- `app/services/gamification_service.py` — `award_xp()`, `check_achievements()`, `update_streak()`
- Wire XP awards: problem solve, interview complete, appropriate hint use, streak maintenance
- `app/routers/gamification.py` — `GET /gamification/me` (internal `POST /gamification/award` not user-facing)
- `tests/test_gamification.py`

---

### Phase 13 — Problem Management & Instructor Endpoints
**Goal**: Problem CRUD (instructor-only writes) + instructor analytics views + AI cohort summary.

**What gets built:**
- `app/models/problem.py` (Problem, ProblemAttempt) + Alembic migration
- `app/repositories/problem_repo.py`
- `app/services/problem_service.py`
- `app/prompt_templates/instructor_summary.py`
- `app/routers/problems.py` — `GET /problems`, `GET /problems/daily`, `GET /problems/recommended`, `POST /problems` (instructor), `GET /problems/{id}/attempts`
- `app/routers/instructor.py` — `GET /instructor/students`, `GET /instructor/students/{id}`, `GET /instructor/common-mistakes`, `POST /instructor/summary`
- Role-based access: instructor role enforced via dependency
- `tests/test_problems.py`

---

### Phase 14 — Hardening
**Goal**: Rate limiting, structured logging, full test sweep, deployment-ready config.

**What gets built:**
- Redis-backed rate limiting on `/mentor/*` and `/execution/*` endpoints (sliding window per user)
- `request_id` middleware — UUID injected into every request log and response header
- `structlog` fully configured: JSON formatter, bound context per request
- Full test pass — every router has: happy path, unauthenticated case, validation-error case
- `.env.example` final review + deployment notes in README
- Docker Compose production profile (health checks, restart policies)
- Piston runtime pre-seeding script (install Python/JS/Java runtimes on first boot)

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Python package manager | `uv` | 10-100x faster than pip; `pyproject.toml` lockfile; modern standard |
| Async ORM | SQLAlchemy 2.0 async | Best pgvector integration; mature Alembic story |
| Test DB | SQLite for unit; real Postgres for integration | Fast unit tests; real behavior tested in integration |
| LLM default model | `gpt-4o-mini` (configurable) | Cost-controlled dev; swap to `gpt-4o` via env var |
| Prompt construction | Dedicated `prompt_templates/` module | Single place to audit what the model sees; no scattered f-strings |
| Background tasks | `FastAPI.BackgroundTasks` (pure functions) | Celery-ready: service methods have no request-scoped state |
| Rate limiting | Redis sliding window | Works across restarts; Redis already in stack |
| Exception handling | Custom hierarchy + global FastAPI handlers | No bare `HTTPException` in services; consistent error shape |

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "ai-coding-mentor"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Web
    "fastapi[standard]>=0.115",
    "uvicorn[standard]>=0.30",

    # DB
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.29",           # async postgres driver
    "aiosqlite>=0.20",         # async sqlite for tests

    # Cache
    "redis[hiredis]>=5.0",

    # Auth
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "authlib>=1.3",
    "httpx>=0.27",             # authlib + test client

    # AI
    "openai>=1.35",

    # Validation / Config
    "pydantic>=2.7",
    "pydantic-settings>=2.3",

    # Logging
    "structlog>=24.2",

    # Linters invoked as subprocesses (installed in Docker image)
    # ruff, eslint, clang-tidy, checkstyle handled via Dockerfile
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "factory-boy>=3.3",        # test data factories
]
```

---

## Docker Compose Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | Persistent volume, `pgvector` extension enabled at init |
| `redis` | `redis:7-alpine` | 6379 | Persistent volume |
| `piston` | `ghcr.io/engineer-man/piston` | 2000 | Self-hosted; runtimes installed via `POST /api/v2/packages` on first boot |
| `app` | `./Dockerfile` | 8000 | Depends on postgres + redis + piston |

---

## Verification Plan

### Per-phase automated
- `pytest tests/test_<phase>.py -v` — all green before moving to next phase
- `pytest --cov=app --cov-report=term-missing` — coverage tracked per phase

### Manual (Swagger UI)
- Each phase ends with explicit `curl` commands you can run against `http://localhost:8000/docs`
- Swagger UI is the primary "frontend" — all endpoints fully documented with response examples

### Integration tests (opt-in)
```bash
RUN_LIVE_INTEGRATION_TESTS=1 pytest tests/ -m integration
```
These hit real local Piston and real OpenAI — only run locally, never in CI.

---

## Environment Variables (.env.example preview)

```dotenv
# App
APP_ENV=development
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# Database
DATABASE_URL=postgresql+asyncpg://mentor:mentor@localhost:5432/mentor_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Piston (self-hosted)
PISTON_URL=http://localhost:2000

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
OAUTH_REDIRECT_BASE_URL=http://localhost:8000

# Execution limits
MAX_CODE_SIZE_KB=256
COMPILE_TIMEOUT_SECONDS=10
RUN_TIMEOUT_SECONDS=15

# Rate limits (per user, per minute)
RATE_LIMIT_EXECUTION=20
RATE_LIMIT_MENTOR=30
```

---
