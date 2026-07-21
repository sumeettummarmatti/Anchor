# Anchor- Steady guidance wherever you
Learning to code can feel like being caught in rough water. Every bug, failed run, and difficult interview sends another wave of doubt, insecurity, and frustration. Anchor keeps learners grounded. It brings coding guidance, step-by-step execution, interview practice, and progress analytics into one connected workspace. Rocky offers help when you need it—without taking over—so every mistake becomes something you can understand and learn from. When the waves push you away from confidence, Anchor holds you steady, guides you back to shore, and helps you keep moving forward.

**Anchor — when the waves rise, keep learning on solid ground.**

# Mentor Workspace

Backend-only FastAPI service for an adaptive coding mentor. It includes JWT auth, project/session
workspaces, Piston execution, Ruff/ESLint static analysis, local-model mentor chat, progressive
hints, and a browser demo UI.
Mentor Workspace is an adaptive coding-practice application that brings four learning experiences into one authenticated browser workspace:

- **Coding Mentor** — write code, run static analysis and execution, ask for explanations, get progressive hints, and work with Rocky, the live tutor.
- **Execution Lab** — replay a Python program step by step, inspect variables and call-stack state, and see a graphical representation of supported data structures.
- **Interview Engine** — turn a submitted solution into an interactive technical interview, receive feedback, and generate a final report.
- **Analytics** — review learning activity, interview results, language usage, and recommended problems.

The application is built with FastAPI. PostgreSQL stores accounts, projects, sessions, executions, hints, and learner profiles; Redis supports live-tutor state; Piston runs submitted code; and an LLM powers mentoring. The interview and trace experiences are supplied by the bundled `interview_engine` module.

## Contents

- [What happens in the workspace](#what-happens-in-the-workspace)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Open and navigate the application](#open-and-navigate-the-application)
- [Detailed tab guide](#detailed-tab-guide)
- [How information moves between tabs](#how-information-moves-between-tabs)
- [Configuration](#configuration)
- [Development and tests](#development-and-tests)
- [API overview](#api-overview)
- [Troubleshooting](#troubleshooting)

## What happens in the workspace

```text
Sign up / log in
      |
      v
An authenticated learning session is created
      |
      +--> Coding Mentor: edit, analyze, run, explain, and request hints
      |          |
      |          +--> Execution Lab: visualise the current code as a trace
      |          |
      |          +--> Interview Engine: interview on the current solution
      |
      +--> Analytics: view activity and choose a recommended problem
                         |
                         +--> Coding Mentor: recommended problem is loaded into the editor
```

Every execution is associated with the active learning session. When a session ends, the application updates the learner profile in the background. That profile adjusts mentor style, hint depth, problem difficulty, and the frequency of live interventions. Recommendations use a trained local bi-encoder when its artifacts are available, otherwise a rule-based fallback.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop with Docker Compose
  with any model loaded in its local server
- One LLM option:
  - **Groq** — required by the bundled Interview Engine. Obtain a Groq API key.


The full workspace uses Piston, PostgreSQL, Redis, and the Interview Engine; Docker Compose starts the first three automatically. The API fails at startup if the Interview Engine cannot find `GROQ_API_KEY`.

## Fresh setup on macOS
## Quick start

Clone the repository and enter it:
These steps run the complete workspace locally on macOS or Linux.

### 1. Clone and configure the project

```bash
git clone <your-repository-url>
cd codex-hackathon
cd openai
cp .env.example .env
```

Edit `.env` and set secure values. At a minimum, set `APP_SECRET_KEY` and your Groq key:

```bash

```dotenv
APP_SECRET_KEY=replace-with-a-long-random-value
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

For a local Uvicorn launch, the bundled Interview Engine reads `interview_engine/.env`. Create or update that file too:

```bash

```dotenv
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

In Terminal 2, start the database, Redis, Piston, and the automatic Piston runtime seeder:
Do not commit either `.env` file or any API key.

### 2. Start infrastructure and code execution

```bash
cd codex-hackathon
docker compose up -d --wait postgres redis piston piston-init
```

The seeder installs Python `3.10.0` and Node `18.15.0` into Piston. The first run can take a few
minutes. Confirm the runtimes are available:
`piston-init` installs the Python 3.10 and Node 18.15 runtimes the application expects. The first run can take a few minutes. Verify the service and installed runtimes:

```bash
docker compose ps
curl http://127.0.0.1:2000/api/v2/runtimes
```

Install Python dependencies, apply migrations, and start the API:
### 3. Install the application and run migrations

```bash
uv sync --all-groups
uv pip install -e ./interview_engine
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The host-run database uses `127.0.0.1:5433` because macOS machines often already have another
Postgres server on port `5432`.
### 4. Start the application

## Docker-only API
```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Use this instead of the local Uvicorn command if you want the API itself inside Docker:
Check that it is available:

```bash
docker compose up -d --build --wait
docker compose exec api alembic upgrade head
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/llm
```

Do not run the Docker API and local Uvicorn API at the same time; both use port `8000`.


## Open the application




Browser demo UI:
Use this configuration in the root `.env`:

```bash
open http://127.0.0.1:8000/demo/


### Docker-only API option

To run the API itself in Docker rather than with local Uvicorn:

```bash
open http://127.0.0.1:8000/docs
docker compose up -d --build --wait
docker compose exec api alembic upgrade head
```

In the demo UI:
Do not start both the Docker API and local Uvicorn: both use port `8000`.

## Open and navigate the application

Open [http://127.0.0.1:8000/merged/](http://127.0.0.1:8000/merged/) in a browser.

1. Choose **Sign up** to create an account, then log in. Returning users can choose **Log in** directly.
2. After login, the workspace opens on **Coding Mentor**. It creates a scratch project and learning session automatically when needed.
3. Use the persistent left sidebar to switch between **Coding Mentor**, **Execution Lab**, **Interview Engine**, and **Analytics**. On narrow screens the navigation becomes a horizontally scrollable row.
4. Use the sun button to switch theme. Use **Log out** to invalidate the refresh token in the browser and return to the sign-in page.

The workspace refreshes the access token periodically while it is open. A signed-in browser session is required for the unified workspace; unauthenticated visitors are sent back to the login screen.

## Detailed tab guide

### 1. Coding Mentor

This is the main practice space. Start by entering a problem title, difficulty, description, and Python code. The default example is Two Sum.

1. Select **Analyze code** to run static analysis. Python analysis uses Ruff.
2. Select **Run code** to send the code to Piston. The response console shows standard output, errors, exit status, execution time, and analysis diagnostics.
3. Read **Explain output** for a plain-language explanation of the result or error.
4. Select **Get next hint** for progressive help. Hints are stored against the active session and must be requested in order.
5. Select **Live Tutor: ON**, or **Turn on Live Agent Rocky**, to enable Rocky. After you pause while editing, Rocky can offer a contextual nudge. Open Rocky's bubble to chat, request a hint, dismiss it, or enter agent mode.

Rocky also offers two shortcuts:

1. Create an account and log in.
2. Create a scratch learning session.
3. Enter Python code and click **Analyze code**.
4. Click **Run code** to execute through Piston.
5. Ask the local mentor a question.
6. Request progressive hints one level at a time.
7. End the session; the learner profile is updated in a background task.
- **Visualise** sends the editor's current code to Execution Lab and opens that tab.
- **Interview** sends the current problem, code, language, difficulty, and latest execution result to Interview Engine and opens that tab.

### 2. Execution Lab

Execution Lab is a Python trace viewer, not the same as the Piston run button in Coding Mentor.

1. Paste Python code, load the example, or arrive here through Rocky's **Visualise** action.
2. Select **Run trace** to construct an execution timeline.
3. Move through the trace with the restart, previous, next, and play controls. Use the 0.5×, 1×, and 2× playback speed controls; left and right arrow keys move one step at a time when you are not editing.
4. Inspect the current statement, AI explanation, variable values, supported graphical structures, call stack, console output, and trace summary.

The trace service deliberately supports safe Python execution only. It can follow functions, classes, recursion, loops, conditionals, selected standard-library imports, runtime exceptions, and replayable state. Filesystem and network built-ins are unavailable.


### 3. Interview Engine

Run the complete automated suite:
Interview Engine uses the solution currently supplied by Coding Mentor, or its built-in Two Sum example if opened directly.

1. Confirm the submitted code, language, and execution result.
2. Select **Start interview**. The coach asks its first technical question.
3. Type an explanation and select **Submit answer** to receive an evaluation and follow-up question.
4. Use **Give answer** for a reference answer, or **Next question** to advance through planned questions. Browser voice features are available when supported: toggle spoken questions and use the microphone to dictate an answer.
5. Select **Finish** to generate a report with an overall score, strengths, and suggested topics to practice.


### 4. Analytics

Analytics aggregates activity recorded from the user's activity. It displays completed interviews, solved problems, average score, active days, score trends, language mix, and recent events.

1. Select **Refresh** to reload the current account's analytics.
2. Select **Refresh recommendations** to retrieve practice suggestions.
3. Select a recommended problem. The workspace switches to Coding Mentor and loads that problem's title, description, difficulty, language, and available starter snippet into the editor.


### Synthetic bi-encoder recommendations
## Development and tests

The recommendation prototype uses deterministic stub learners and a 48-problem catalog. This is
development data only; retrain it on real analytics events before treating scores as product
recommendations. Train the local CPU model with:
Run the main lint and test suite:

```bash
uv run python -m app.ml.train_recommender --epochs 20
uv run ruff check app tests
uv run pytest -q
```

The command writes ignored artifacts under `artifacts/recommender/` and prints top-five results
for `fast_clean_solver`, `steady_builder`, and `frequent_stuck`. The API loads those artifacts
lazily. Without them, the endpoint remains available using a rule-based fallback:
Useful focused checks:

```bash
curl "http://127.0.0.1:8000/problems/recommended?k=5" \
  -H "Authorization: Bearer <access-token>"
uv run pytest tests/test_static_analysis.py -q
uv run pytest tests/test_mentor.py -q
uv run pytest tests/test_personalization.py -q
uv run pytest tests/test_recommendation_service.py -q
uv run pytest interview_engine/tests -q
```

Each result contains `source: "bi_encoder"` after training or `source: "rule_fallback"` before
training. The test that checks the directional signal is:
Train the optional local recommendation model with synthetic development data:

```bash
uv run pytest tests/test_recommendation_service.py -q
uv run python -m app.ml.train_recommender --epochs 20
```

All endpoints except health and the public auth routes require an access token. Swagger can send
the token after using the **Authorize** button.
Artifacts are written to `artifacts/recommender/`. Before training, recommendations remain available through the rule-based fallback; after training, results identify `source: "bi_encoder"`.