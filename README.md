# AI Coding Mentor API

Backend-only FastAPI service for an adaptive coding mentor. It includes JWT auth, project/session
workspaces, Piston execution, Ruff/ESLint static analysis, local-model mentor chat, progressive
hints, and a browser demo UI.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Docker Desktop with Docker Compose
- [Ollama](https://ollama.com/download) with the `qwen3:8b` model, or [LM Studio](https://lmstudio.ai/)
  with any model loaded in its local server

The default LLM is local Ollama. If Ollama is unavailable or times out, the API automatically
tries LM Studio. No OpenAI key is required for either local provider.

## Fresh setup on macOS

Clone the repository and enter it:

```bash
git clone <your-repository-url>
cd codex-hackathon
cp .env.example .env
```

Install and verify the local model:

```bash
ollama pull qwen3:8b
ollama list
```

Keep Ollama running in Terminal 1:

```bash
ollama serve
```

In Terminal 2, start the database, Redis, Piston, and the automatic Piston runtime seeder:

```bash
cd codex-hackathon
docker compose up -d --wait postgres redis piston piston-init
```

The seeder installs Python `3.10.0` and Node `18.15.0` into Piston. The first run can take a few
minutes. Confirm the runtimes are available:

```bash
curl http://127.0.0.1:2000/api/v2/runtimes
```

Install Python dependencies, apply migrations, and start the API:

```bash
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The host-run database uses `127.0.0.1:5433` because macOS machines often already have another
Postgres server on port `5432`.

## Docker-only API

Use this instead of the local Uvicorn command if you want the API itself inside Docker:

```bash
docker compose up -d --build --wait
docker compose exec api alembic upgrade head
```

Do not run the Docker API and local Uvicorn API at the same time; both use port `8000`.

## Open the application

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Browser demo UI:

```bash
open http://127.0.0.1:8000/demo/
```

Swagger API documentation:

```bash
open http://127.0.0.1:8000/docs
```

In the demo UI:

1. Create an account and log in.
2. Create a scratch learning session.
3. Enter Python code and click **Analyze code**.
4. Click **Run code** to execute through Piston.
5. Ask the local mentor a question.
6. Request progressive hints one level at a time.
7. End the session; the learner profile is updated in a background task.

## Phase 5, 6, and 7 tests

Run the complete automated suite:

```bash
uv run ruff check app tests
uv run pytest -q
```

Phase-specific tests:

```bash
uv run pytest tests/test_static_analysis.py -q
uv run pytest tests/test_mentor.py -q
uv run pytest tests/test_personalization.py -q
```

The mentor unit tests mock the LLM provider. The running application uses Ollama first and falls
back to LM Studio through OpenAI-compatible endpoints:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_API_KEY=ollama
OLLAMA_MODEL=qwen3:8b
OLLAMA_THINK=false
OLLAMA_NUM_PREDICT=512
LLM_REQUEST_TIMEOUT_SECONDS=60
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_API_KEY=lm-studio
LMSTUDIO_MODEL=
```

Leave `LMSTUDIO_MODEL` empty to automatically use the first model returned by
`http://localhost:1234/v1/models`. Set `LLM_PROVIDER=lmstudio` to use LM Studio only, or
`LLM_PROVIDER=auto` to explicitly enable the Ollama-then-LM Studio order.

## API endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /auth/register` | Create a learner account |
| `POST /auth/login` | Obtain access and refresh tokens |
| `POST /projects` | Create a coding project |
| `POST /sessions` | Start a learning session |
| `POST /static-analysis/run` | Run Ruff or ESLint analysis |
| `POST /execution/run` | Analyze and execute code through Piston |
| `POST /mentor/chat` | Ask a Socratic mentor question |
| `POST /mentor/hint` | Request the next progressive hint |
| `POST /mentor/explain-error` | Explain a runtime or compiler error |
| `GET /users/me/profile` | Read the learner's adaptive profile |
| `GET /problems/recommended` | Retrieve personalized stub-problem recommendations |

### Learner profile and personalization

Starting a session automatically creates a default profile for the authenticated learner. Ending
the session schedules a non-blocking profile update using execution and hint history. The profile
controls mentor teaching style, hint-depth ceiling, difficulty adjustment, and intervention
frequency. Mentor chat, hints, and error explanations include this adaptation context automatically.

Inspect the current profile with:

```bash
curl http://127.0.0.1:8000/users/me/profile \
  -H "Authorization: Bearer <access-token>"
```

### Synthetic bi-encoder recommendations

The recommendation prototype uses deterministic stub learners and a 48-problem catalog. This is
development data only; retrain it on real analytics events before treating scores as product
recommendations. Train the local CPU model with:

```bash
uv run python -m app.ml.train_recommender --epochs 20
```

The command writes ignored artifacts under `artifacts/recommender/` and prints top-five results
for `fast_clean_solver`, `steady_builder`, and `frequent_stuck`. The API loads those artifacts
lazily. Without them, the endpoint remains available using a rule-based fallback:

```bash
curl "http://127.0.0.1:8000/problems/recommended?k=5" \
  -H "Authorization: Bearer <access-token>"
```

Each result contains `source: "bi_encoder"` after training or `source: "rule_fallback"` before
training. The test that checks the directional signal is:

```bash
uv run pytest tests/test_recommendation_service.py -q
```

All endpoints except health and the public auth routes require an access token. Swagger can send
the token after using the **Authorize** button.

## Configuration

The committed `.env.example` documents all settings. Copy it to `.env`; never commit `.env` or
API keys. Supported LLM providers are Ollama (default with LM Studio fallback), LM Studio, OpenAI,
Groq, and Hugging Face. Local providers use one bounded request with no hidden SDK retries, so a
failed Ollama request can fall through promptly. Start LM Studio's local server with its
OpenAI-compatible API enabled; the loaded model is discovered automatically when
`LMSTUDIO_MODEL` is blank.

## Troubleshooting

### Postgres reports `role "mentor" does not exist`

This usually means an old development volume was initialized with different credentials. This
deletes only this project's local database volume; it preserves the Piston runtime cache:

```bash
docker compose down
docker volume rm codex-hackathon_postgres_data
docker compose up -d --wait postgres redis piston piston-init
uv run alembic upgrade head
```

### Execution says `Code execution service is unavailable`

Check that Piston is running and has runtimes:

```bash
docker compose ps
curl http://127.0.0.1:2000/api/v2/runtimes
docker compose logs -f piston
```

If the runtime list is empty, run:

```bash
docker compose run --rm piston-init
```

### Ollama logs

When Ollama is started manually, logs appear in its terminal. To save and follow them:

```bash
ollama serve 2>&1 | tee ~/ollama-server.log
tail -f ~/ollama-server.log
```

### View API logs

```bash
docker compose logs -f api
```

## Stop services

Stop the API and dependencies:

```bash
docker compose down
```

Press `Ctrl+C` in the Ollama terminal to stop Ollama.
