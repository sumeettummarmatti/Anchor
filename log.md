## 2026-07-17 00:00

### Completed
- Created the Phase 1 backend foundation with FastAPI, uv project metadata, Docker Compose, Alembic scaffolding, structured logging, custom application exceptions, and a Swagger-visible health endpoint.
- Added a provider-neutral AI configuration boundary with OpenAI `gpt-4o-mini` as the default and Groq, Hugging Face, and LM Studio options.
- Defined the authentication foundation: HS256 (HMAC-SHA-256) JWT signing, bcrypt password hashing, and SHA-256 refresh-token hashing.

### Files Added
- Project configuration, Docker files, application skeleton, Alembic scaffold, health tests, documentation, and environment template.

### Files Modified
- None; this was an empty workspace.

### Decisions
- Use HS256 for self-issued JWTs and store only SHA-256 refresh-token digests.
- Keep all LLM selection in `AIService`; mentor routes will not call provider SDKs directly.
- Defer database model migrations until Phase 2, when the first persistent auth entities are introduced.

### Known Limitations
- Only `/health` is implemented; no external service is required for it.
- OAuth flows, database entities, Piston execution, and mentor endpoints are intentionally deferred to later confirmed phases.

### TODO / Next Recommended Step
- Confirm Phase 1, then implement Phase 2 authentication and users with its first Alembic migration.

## 2026-07-17 00:40

### Completed
- Added a pinned `requirements.txt` containing every direct runtime, test, and lint dependency resolved for this project.

### Files Added
- `requirements.txt`

### Files Modified
- `log.md`

### Decisions
- Keep `uv.lock` as the authoritative full transitive lockfile; `requirements.txt` is a portable list of direct dependencies pinned to the same resolved versions.

### Known Limitations
- `requirements.txt` intentionally does not duplicate every transitive dependency because pip resolves those automatically.

### TODO / Next Recommended Step
- Continue using `uv sync --all-groups` for reproducible development environments.

## 2026-07-17 00:59

### Completed
- Implemented Phase 2 authentication and users: registration, login, access/refresh JWT issuance, refresh rotation, logout revocation, current-user retrieval, and display-name updates.
- Added Google/GitHub OAuth login and callback routes, including explicit configuration failures when credentials are absent.
- Added the first Alembic migration for `users` and `refresh_tokens` and verified it matches the SQLAlchemy metadata.

### Files Added
- `app/models/user.py`
- `app/repositories/user_repository.py`
- `app/schemas/auth.py`
- `app/schemas/users.py`
- `app/core/dependencies.py`
- `app/services/oauth_service.py`
- `alembic/versions/20260717_0001_create_auth_tables.py`
- `tests/conftest.py`
- `tests/test_auth.py`

### Files Modified
- Authentication, router, application, dependency, migration, configuration, lockfile, requirements, README, and plan files.

### Decisions
- Access and refresh JWTs use HS256; each refresh token includes a unique `jti` so rotation is collision-free.
- Refresh tokens are persisted only as SHA-256 hashes and revoked on rotation/logout.
- Pin `bcrypt` to 4.0.1 because it is compatible with the required `passlib` version.

### Known Limitations
- Live Google/GitHub OAuth exchanges are not exercised without real credentials; unconfigured-provider behavior is covered by tests.
- The Phase 2 test suite uses SQLite; the migration was additionally checked against a fresh SQLite schema. Production remains PostgreSQL.

### TODO / Next Recommended Step
- Confirm Phase 2, then implement Phase 3 projects, files, and session event ingestion.

## 2026-07-17 01:05

### Completed
- Updated Alembic to run migrations through SQLAlchemy's async engine and the existing `asyncpg` driver.

### Files Added
- None.

### Files Modified
- `alembic/env.py`
- `.env`
- `.env.example`
- `docker-compose.yml`
- `log.md`

### Decisions
- Do not add `psycopg2`; the project already uses async SQLAlchemy and `asyncpg` at runtime.

### Known Limitations
- Running the migration still requires a reachable PostgreSQL service matching `DATABASE_URL`.

### TODO / Next Recommended Step
- Start the Docker Compose database services, then run `uv run alembic upgrade head`.

## 2026-07-17 01:15

### Completed
- Corrected the initial PostgreSQL migration so the `user_role` enum is created exactly once.
- Aligned SQLAlchemy's `UserRole` persistence with PostgreSQL's lowercase enum values.

### Files Added
- None.

### Files Modified
- `alembic/versions/20260717_0001_create_auth_tables.py`
- `app/models/user.py`
- `log.md`

### Decisions
- Persist enum `.value` strings (`student`, `instructor`) instead of Python enum names (`STUDENT`, `INSTRUCTOR`).

### Known Limitations
- A running API process must be restarted to load this ORM correction.

### TODO / Next Recommended Step
- Re-run the live registration check against PostgreSQL after restarting the API.

## 2026-07-17 01:16

### Completed
- Started the local PostgreSQL and Redis Compose services and applied the auth migration to real PostgreSQL.
- Confirmed Alembic reports revision `20260717_0001 (head)` and no pending schema changes.
- Ran the API on an isolated local port and verified registration and login against PostgreSQL end-to-end.
- Ran the full test suite successfully.

### Files Added
- None.

### Files Modified
- `log.md`

### Decisions
- Retain the local development database service for the user's subsequent Phase 2 API work.

### Known Limitations
- The pre-existing API process on port 8000 was not stopped; it must be restarted by its owner to load the enum correction.

### TODO / Next Recommended Step
- Restart the API on port 8000 and continue with manual Swagger checks or Phase 3 after confirming Phase 2.

## 2026-07-17 01:18

### Completed
- Added a lightweight, same-origin development UI for visual Phase 2 API testing.
- Added automated coverage confirming the demo UI is served by FastAPI.

### Files Added
- `app/static/index.html`

### Files Modified
- `app/main.py`
- `tests/test_health.py`
- `log.md`

### Decisions
- Keep the page under `/demo/` as a development-only API demonstrator, not as a production frontend.

### Known Limitations
- The demo stores its access token in browser local storage for convenience and must not be used as a production authentication pattern.

### TODO / Next Recommended Step
- Open `/demo/` and use its register, login, and profile actions to inspect Phase 2 visually.

## 2026-07-17 00:38

### Completed
- Generated `uv.lock`, installed the declared dependency set through uv, and verified the foundation with Ruff and pytest.
- Isolated the debug setting as `APP_DEBUG` to prevent an unrelated host `DEBUG` environment variable from breaking startup.

### Files Added
- `uv.lock`

### Files Modified
- `pyproject.toml`
- `.env.example`
- `app/core/config.py`
- `app/main.py`

### Decisions
- Explicitly declared the `app` package as Hatch's wheel target so editable uv installs work predictably.
- Use `APP_DEBUG` instead of a generic `DEBUG` variable.

### Known Limitations
- Pytest emits upstream Python 3.14 event-loop deprecation warnings; tests still pass.

### TODO / Next Recommended Step
- Confirm Phase 1, then implement Phase 2 authentication and users with its first Alembic migration.
