# Independent AI Technical Interview Engine

Standalone FastAPI backend with two independent feature modules: the Interview Engine and the Execution Intelligence/Visualization Engine.

## Layout

```text
interview_engine/
├── app/
│   ├── main.py
│   ├── core/             # config, auth, Groq client
│   ├── interview/        # Phase 9 feature
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── routers/
│   │   ├── prompts/
│   │   └── assets/
│   ├── visualization/    # Execution Intelligence feature
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── routers/
│   │   ├── prompts/
│   │   └── assets/
│   └── frontend/         # Static browser UI
├── tests/
├── setup.py
├── README.md
└── log.md
```

## Run

```bash
cd /Users/tan/Documents/Hacl
python3 -m venv interview_engine/.venv
source interview_engine/.venv/bin/activate
python -m pip install -e ./interview_engine
python -m uvicorn interview_engine.app.main:app --reload
```

If you are already inside `/Users/tan/Documents/Hacl/interview_engine`, launch with
`PYTHONPATH=.. python -m uvicorn interview_engine.app.main:app --reload`.

If you also want to run the test suite, install the development tools with
`python -m pip install pytest httpx`, then run it from `/Users/tan/Documents/Hacl`.

Open `/docs` for Swagger. Groq is required for application startup; deterministic logic remains available as a service-level fallback for isolated tests and provider failures.

## API

- `POST /interview/start` with `{ "context": SubmissionContext, "company": "amazon", "style": "FAANG" }`
- `POST /interview/{id}/answer` with `{ "answer": "..." }`
- `POST /interview/{id}/finish`
- `GET /interview/{id}`
- `GET /interview/{id}/report`
- `POST /visualization/trace` with `{ "language": "python", "source_code": "..." }`
- `GET /visualization/{id}` for the complete replayable timeline
- `GET /visualization/{id}/steps` for ordered execution steps
- `GET /visualization/{id}/summary` for execution summary
- `GET /visualization/{id}/steps/{step}` for a step and its explanation

The repository is in-memory by default. For restart-safe local persistence, use `INTERVIEW_REPOSITORY=sqlite` and optionally set `INTERVIEW_SQLITE_PATH=./interviews.sqlite3`.

The visualization module is independent from the interview module. It currently supports Python snippets, functions, classes, recursion, loops, conditionals, selected safe standard-library imports, runtime exceptions, and replayable state. Unsafe filesystem/network builtins remain unavailable because production arbitrary-code execution should run in an OS/container sandbox.

## Groq-powered AI

Groq is required for the application. Set `GROQ_API_KEY` before starting the server to enable model-assisted planning, answer evaluation, interview reports, execution-step explanations, and execution summaries. `GROQ_MODEL` defaults to `llama-3.3-70b-versatile`. The server fails at startup with a clear configuration error if the key is missing.

The prototype API requires `X-API-Key` and `X-User-ID` headers. The local default key is `dev-api-key`; set `INTERVIEW_API_KEY` to change it. The frontend sends these local-development headers automatically.

The evaluator fallback is a coarse structural heuristic used only when no LLM is available. It is not a fair grading system; configure Groq for substantive evaluation.

```bash
export GROQ_API_KEY="your-key"
export GROQ_MODEL="llama-3.3-70b-versatile"
python -m uvicorn interview_engine.app.main:app --reload
```

Startup logs state whether Groq or fallback mode is active. The default local API key is `dev-api-key`; change it with `INTERVIEW_API_KEY`.

## Browser UI

Open `http://127.0.0.1:8000/` while the server is running. The UI includes the execution lab and the Phase 9 Interview Coach flow.
