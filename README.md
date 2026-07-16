# AI Coding Mentor API

Backend-only FastAPI service for an adaptive AI coding mentor. Swagger UI is at `/docs`.

## Quick start

1. Copy `.env.example` to `.env` and set secrets/provider keys as needed.
2. Install dependencies with `uv sync --all-groups`.
3. Run locally with `uv run uvicorn app.main:app --reload`.
4. Check `http://localhost:8000/health` and `http://localhost:8000/docs`.

For the complete local stack, run `docker compose up --build`.

## LLM provider selection

`LLM_PROVIDER` selects the provider used by the internal `AIService`:

| Value | Required configuration | Default model |
| --- | --- | --- |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| `huggingface` | `HF_API_KEY` | `meta-llama/Llama-3.3-70B-Instruct` |
| `lmstudio` | local server at `LMSTUDIO_BASE_URL` | `local-model` |

The selection is centralized in `app/services/ai_service.py`; routes will never call a provider SDK directly.

## Authentication decision

Local access and refresh tokens use HS256 (HMAC-SHA-256) signed JWTs. Passwords use bcrypt; refresh-token records store only a SHA-256 digest. Google/GitHub OAuth client credentials are loaded from environment variables.

## Auth endpoints

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, and `/auth/logout`
- `GET /auth/oauth/google/login` and `/auth/oauth/github/login`, with matching callback routes
- `GET /users/me` and `PATCH /users/me` (Bearer access token required)

Run `uv run alembic upgrade head` before using the auth endpoints against PostgreSQL. Set the Google or GitHub OAuth variables in `.env` before starting either provider flow.
