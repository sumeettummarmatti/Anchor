# AI Coding Mentor API

Backend-only FastAPI service for an adaptive AI coding mentor. Swagger UI is at `/docs`.

## Quick start

1. Copy `.env.example` to `.env` and set secrets/provider keys as needed.
2. Install dependencies with `uv sync --all-groups`.
3. Run locally with `uv run uvicorn app.main:app --reload`.
4. Check `http://localhost:8000/health` and `http://localhost:8000/docs`.

## Fresh local setup

Start Ollama in a separate terminal and confirm the local model is available:

```bash
ollama serve
ollama list
```

For a host-run FastAPI server, start the dependencies and wait for their health checks before
running migrations:

```bash
docker compose up -d --wait postgres redis piston piston-init
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

If a fresh setup reports `role "mentor" does not exist`, an older local Postgres volume is being
reused. This removes only this project's development database (not the Piston runtime cache):

```bash
docker compose down
docker volume rm codex-hackathon_postgres_data
docker compose up -d --wait postgres redis piston piston-init
uv run alembic upgrade head
```

The host-run database URL is `127.0.0.1:5433`, rather than the common `localhost:5432`: this
avoids a locally installed Postgres taking precedence over Docker's port mapping on macOS.

To run the complete stack in Docker instead, use:

```bash
docker compose up -d --build --wait
docker compose exec api alembic upgrade head
```

## LLM provider selection

`LLM_PROVIDER` selects the provider used by the internal `AIService`:

| Value | Required configuration | Default model |
| --- | --- | --- |
| `ollama` (default) | local Ollama server at `OLLAMA_BASE_URL` | `qwen3:8b` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `huggingface` | `HF_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct` |
| `lmstudio` | local server at `LMSTUDIO_BASE_URL` | `local-model` |

The selection is centralized in `app/services/ai_service.py`; routes will never call a provider SDK directly.

For local development, start Ollama before the API (`ollama serve`) and ensure the configured
model is present (`ollama pull qwen3:8b`). Docker Compose connects the API container to Ollama on
the host at `host.docker.internal:11434`.

## Authentication decision

Local access and refresh tokens use HS256 (HMAC-SHA-256) signed JWTs. Passwords use bcrypt; refresh-token records store only a SHA-256 digest. Google/GitHub OAuth client credentials are loaded from environment variables.

## Auth endpoints

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, and `/auth/logout`
- `GET /auth/oauth/google/login` and `/auth/oauth/github/login`, with matching callback routes
- `GET /users/me` and `PATCH /users/me` (Bearer access token required)

Run `uv run alembic upgrade head` before using the auth endpoints against PostgreSQL. Set the Google or GitHub OAuth variables in `.env` before starting either provider flow.

## Static analysis and mentor endpoints

`POST /static-analysis/run` runs Ruff for Python and ESLint when it is installed. Each
`POST /execution/run` response now includes the same normalized analysis result and persists it.

The protected mentor endpoints are `POST /mentor/chat`, `/mentor/hint`, and
`/mentor/explain-error`. Hints require a learning-session ID and must be used in order;
run `uv run alembic upgrade head` to create the `hint_events` table.
