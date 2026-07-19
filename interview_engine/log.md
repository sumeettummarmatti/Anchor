# Interview Engine Log

## 2026-07-17

Implemented:
- Added standalone FastAPI API, SubmissionContext contract, schemas, and assets.
- Added deterministic state machine, repository boundary, planner/interviewer/evaluator/follow-up/report services.
- Added local mock AI behavior and testable dependency injection.

Decision:
- Backend owns state transitions and persistence; AI services only return structured content.
- In-memory storage is the default so the module runs without platform dependencies.

Next:
- Add a production SQLite/Postgres repository and an authenticated LLM adapter.

Fix:
- Added legacy setuptools metadata for editable installs with older pip versions.
- Corrected launch instructions to run with the workspace parent on the import path.

## 2026-07-18

Completed:
- Added independent Visualization / Execution Intelligence module with Python tracing, event parsing, timeline replay, variable histories, annotations, and summaries.
- Added visualization repository, service layer, prompt modules, static assets, schemas, and tests.

APIs:
- Added `POST /visualization/trace`, complete trace, steps, summary, and step-explanation endpoints.

Decision:
- Tracing and AI explanation are separate injectable services; the default explainer is deterministic and local.
- Python execution uses a restricted builtin set and finite event budget; production untrusted execution needs an OS/container sandbox.

Fix:
- Corrected zero-based variable-history indexing during timeline construction.

Next:
- Add persistent trace storage, production sandboxing, and a real AI provider adapter.

## 2026-07-18 — UI

Completed:
- Added a dependency-light browser UI served from `/` with an execution lab, timeline controls, variable/call-stack/output panels, and step explanations.
- Added placeholder navigation surfaces for Interview Coach and Analytics.

Decision:
- UI uses the existing REST APIs directly and is served as static assets by FastAPI; no separate frontend build system is required for the placeholder phase.

## 2026-07-18 — Groq and Phase 9 UI

Completed:
- Added a Groq OpenAI-compatible client with environment configuration and deterministic fallback behavior.
- Connected Groq-backed generation to interview planning, evaluation, reporting, execution explanations, and summaries.
- Added a working Phase 9 interview UI with start, answer, finish, and report flows.
- Made the execution editor blank by default with an optional example loader; arbitrary supported Python source is sent to the backend.

Decision:
- The backend owns provider selection and JSON validation; the frontend never receives the Groq key.
- Python tracing permits a small standard-library allowlist while keeping unsafe filesystem/network builtins unavailable.
- Fixed static frontend mounting order so `/health`, `/docs`, and API routes remain reachable.
- Fixed class/function tracing by providing the Python class-construction runtime and common exception/introspection builtins.
- Added explicit `groq` versus `local_fallback` annotation metadata and surfaced it in the UI.

## 2026-07-18 — Remediation Tasks 8–12

Completed:
- Added one schema-repair LLM call before fallback for malformed evaluator, report, planner, follow-up, and execution-summary JSON.
- Added `SQLiteInterviewRepository` with environment selection and persistence for interviews, messages, evaluations, and reports.
- Added non-blocking per-interview locks for answer and finish mutations.
- Interview Coach UI now displays evaluation scores/feedback, follow-ups, and final reports.
- Added startup logs for Groq-enabled versus fallback mode and repository selection.

Verification:
- Invalid evaluator JSON repairs successfully on the second LLM call.
- Fresh SQLite repository reloads an existing interview.
- Overlapping answer calls produce one success and one conflict.
- Service compilation and direct smoke checks pass.

## 2026-07-18 — Remediation Task 13

Implemented:
- Added regression coverage for JSON repair, SQLite persistence, concurrent mutations, authentication, follow-up behavior, tracer sandboxing, and fallback evaluator robustness.

Verification:
- Python compilation and combined integration smoke checks pass.
- Startup logs verified in both fallback mode and configured Groq mode.
- Full pytest command remains blocked because `pytest` is not installed in the current virtualenv; install with `python -m pip install -e '.[dev]'` before running it.

## 2026-07-18 — Master Fix Task 1

Implemented:
- Added `python-dotenv` to runtime dependencies.
- Loads the package-local `.env` before settings and Groq configuration are initialized.

Verification:
- A temporary `.env` with a test key produced `AI mode: GROQ enabled` on plain module startup.
- The temporary test `.env` was removed; no secret was committed.

## 2026-07-18 — Groq Required

Implemented:
- Made `GROQ_API_KEY` mandatory for application startup.
- Removed silent fallback-mode startup from `app/main.py`; missing configuration now raises a clear error.
- Classified Groq HTTP 401/403 as permanent credential errors instead of retrying and hiding them behind fallback responses.

## 2026-07-18 — Remediation Task 1

Completed:
- Moved submitted Python execution into a separate forked worker process.
- Added parent wall-clock termination, CPU/resource limits where supported, finite trace budget, and dangerous dunder AST rejection.

Verification:
- `().__class__.__base__.__subclasses__()` is rejected.
- `while True: pass` is terminated within the bounded wall timeout.
- Class definitions and methods still trace successfully in the worker.

Residual risk:
- `resource.RLIMIT_AS` is not changeable on some macOS Python builds; the parent wall timeout remains enforced. Production deployment should use an OS/container sandbox with network and filesystem isolation.

Next:
- Wait for confirmation before starting Remediation Task 2 (authentication and ownership checks).

## 2026-07-18 — Remediation Task 2

Completed:
- Added swappable API-key authentication via `X-API-Key` and caller identity via `X-User-ID`.
- Protected all interview and visualization routes.
- Added interview ownership checks returning 403 for another user's interview.
- Updated the frontend and API regression tests to send prototype credentials.

Verification:
- Missing credentials produce 401.
- Valid credentials resolve the authenticated user.
- Protected interview and visualization routes are registered with the auth dependency.
- HTTP ownership tests were added but not executed because `httpx` is not installed in the current virtualenv.

Next:
- Wait for confirmation before starting Remediation Task 3 (question index and follow-up state).

## 2026-07-18 — Remediation Task 3

Implemented:
- Split planned-question position, total answer turns, and consecutive follow-up count.
- Added a maximum of two consecutive follow-ups per planned question.
- Allowed the valid `WAITING_FOR_ANSWER → QUESTIONING` transition when advancing to the next planned question.

Verification:
- A follow-up on planned question 1 now proceeds to planned question 2 after resolution.
- An always-low/always-follow-up evaluator reaches planned question 2 after the two-follow-up cap.
- Service smoke checks and Python compilation pass.

Next:
- Wait for confirmation before starting Remediation Task 4 (context-aware follow-ups).

## 2026-07-18 — Remediation Task 4

Implemented:
- Added LLM-backed, question/answer-grounded follow-up generation.
- Loaded `assets/followup_templates.json` and selected fallback prompts for vague answers, missing complexity, missing edge cases, and trade-offs.

Verification:
- Vague and complexity-blind low-scoring answers produce different fallback questions.
- Follow-up template loading and fallback selection smoke test passes.
- The application injects the configured LLM into `FollowupGenerator`.

## 2026-07-18 — Remediation Task 5

Implemented:
- Enriched `SubmissionContext` with execution status, pass/fail flag, struggle indicators/level, code line count, and output presence.
- Passed enriched context into planning and retained it for evaluator/report prompts.

Verification:
- A failed, multi-attempt, hint-assisted submission reaches the planner with `struggle_level=high` and all derived indicators.

## 2026-07-18 — Remediation Task 6

Implemented:
- Added centralized LLM retry/logging with one retry for transient transport failures.
- Added distinct warning/error logs for transport, unexpected, JSON, and schema failures.
- Removed silent LLM exception swallowing from planner, evaluator, follow-up, report, step explainer, and summary services.
- Added `provider_used` to evaluations/reports and provider metadata to execution annotations/summaries.

Verification:
- Simulated timeout retries exactly once and emits transient failure logs.
- Simulated invalid JSON emits a distinct response/schema failure log and falls back.

## 2026-07-18 — Remediation Task 7

Implemented:
- Replaced keyword-only fallback scoring with structural/coherence checks, plausible Big-O phrasing, code-identifier overlap, and caps.
- Documented that fallback scores are coarse heuristics, not fair grading.

Verification:
- Long repeated keyword-stuffed answers score below the top range and receive fallback-heuristic feedback.

## 2026-07-18 — Structure Cleanup

Implemented:
- Moved shared infrastructure into `app/core`.
- Grouped Phase 9 interview code under `app/interview`.
- Grouped execution intelligence and visualization code under `app/visualization`.
- Moved the browser UI into `app/frontend` and updated package/import paths.
- Added a project `.gitignore` for local environments, secrets, databases, caches, and build output.

Verification:
- Application import, service wiring, and Python tracer smoke test pass from the project root.

## 2026-07-18 — Master Fix v2 Task 1

Implemented:
- Fixed the tracer parent process so it drains the multiprocessing pipe while the worker is running.
- Prevented large trace payloads from deadlocking before `join()` and being reported as false timeouts.
- Added a regression test for trace results larger than the pipe buffer.

Verification:
- Large-payload trace completed with 11 events in 0.010s.
- Class/method-heavy BST trace completed with 157 events in 0.003s.

## 2026-07-18 — Voice/Visualization Addition Task 1

Implemented:
- Added 0.5×, 1×, and 2× playback speed controls beside the replay controls.
- Added `state.playSpeed` with a 1× default and changed the base playback interval to 1000ms.
- Changing speed during playback restarts only the timer and preserves the current step.

Verification:
- Static checks confirm all three controls, speed state, timer restart logic, and removal of the old 700ms interval.
- Full pytest and browser click-through remain unavailable because pytest is not installed and the local server is isolated from the browser sandbox.

## 2026-07-18 — Voice/Visualization Addition Task 2

Implemented:
- Added browser-native TTS for AI interview messages with a session-only voice on/off toggle.
- Added feature-detected Speech Recognition that appends interim/final transcripts into the existing answer textarea without auto-submitting.
- Added graceful unsupported-browser messaging and a recording indicator.
- Stops speech recognition/TTS when recording starts, the interview ends, the user leaves Interview Coach, or the page unloads.

Verification:
- Frontend static checks and Python compilation pass.
- Full pytest and live browser voice checks remain unavailable because pytest is not installed and the local server is isolated from the browser sandbox.

## 2026-07-18 — Voice/Visualization Addition Task 3

Implemented:
- Extended tracer snapshots for user-defined execution objects with `__ref__`, `__type__`, and recursive `attrs` data.
- Added cycle references and depth/object-count caps to prevent recursive or pathological structures from expanding without bound.
- Preserved existing primitive, list, tuple, set, dict, and opaque-value snapshot behavior.
- Added a regression test for a cyclic linked structure.

Verification:
- Cyclic `Node` graph smoke test passes with structured attributes and cycle markers.
- BST-style object trace, large-pipe trace, and depth-cap compatibility checks pass.

## 2026-07-18 — Voice/Visualization Addition Task 4

Implemented:
- Added an inline SVG Structure View beside the Variables panel.
- Added tree, linked-list, generic graph, and primitive-array layouts from trace snapshots.
- Added directed edges, node labels, changed-node highlighting, and SVG position animations during replay.
- Kept the existing Variables panel unchanged and updated the Structure View through the same step/playback path.

Verification:
- Frontend static checks confirm graph extraction, layout selection, SVG rendering, highlighting, animation, and panel wiring.
- Backend object-graph, BST, large-pipe, depth-cap, and Python compilation checks pass.

## 2026-07-18 — Structure View Layout Correction

Implemented:
- Filtered layout roots to nodes with no incoming structural edge instead of treating every top-level snapshot reference as a root.
- Added level-aware tree sizing so nodes have vertical depth and enough horizontal spacing to avoid box overlap.
- Updated linked-list/generic height calculations and changed-node fallback highlighting to use structural roots.

Verification:
- BST trace inspection confirms 8 nodes, 7 edges, and a single structural root before rendering.
- Layout static checks and backend trace checks pass.

## 2026-07-19 — Phase 11 Milestone 1: Event Infrastructure

Implemented:
- Added `app/analytics` with immutable `AnalyticsEvent`, append-only in-memory storage, and synchronous sqlite3 storage.
- Added JSON-configured event types covering interview, execution, mentor, project, session, and problem activity.
- Added `EventProcessor`, `EventPublisher`, `NullEventPublisher`, Pydantic ingestion/response schemas, and authenticated `POST /analytics/events`.
- Added keyword-only no-op publisher compatibility parameters to `InterviewService` and `VisualizationService` without changing their business logic.
- Registered the analytics event processor/router in `app/main.py` with `ANALYTICS_REPOSITORY=memory|sqlite` support.

Architectural decisions:
- Events are immutable and append-only; derived analytics will be computed from them in later milestones.
- No ORM or migration tool was introduced, deliberately matching the existing hand-rolled synchronous repository architecture.

Verification:
- Application import, route registration, event normalization, JSON-configured custom event types, publisher/null-publisher compatibility, in-memory storage, sqlite storage, duplicate rejection, and Python compilation pass.
- Full pytest/TestClient execution is blocked because the virtualenv lacks `pytest` and `httpx`.

Next planned milestone:
- Build aggregation, snapshots, weekly/monthly reports, and progress calculations from persisted events.

## 2026-07-19 — Analytics Overview and Frontend Integration

Implemented:
- Added aggregation, snapshot, and progress services computed from append-only events.
- Added authenticated `GET /analytics/me`, `/analytics/me/weekly`, `/analytics/me/monthly`, and `/analytics/me/progress` endpoints.
- Wired interview start, answer, and completion events plus trace lifecycle events into the real analytics publisher.
- Replaced the Analytics placeholder with a data-backed dashboard containing totals, score trend, language mix, recent activity, and refresh behavior.

Architectural decisions:
- The dashboard reads only from analytics events; no derived values are manually maintained.
- Trace events now use the authenticated visualization user when created through the API, while direct service calls retain a safe `system` default.

Verification:
- Analytics aggregation smoke test confirms user scoping, interview scores, trace counts, language detection, score change, and recent activity.
- Application compilation, route registration, event publisher wiring, and frontend static checks pass.
- Full pytest/TestClient and live browser verification remain blocked because `pytest`/`httpx` are not installed and the local server is isolated from the browser sandbox.

## 2026-07-19 — Analytics Layout Fix

Implemented:
- Added cache-busted stylesheet and script URLs so the browser loads the current Analytics styles and behavior.
- Fixed metric card sizing, four-column desktop layout, responsive two-column/mobile behavior, and chart column sizing.

Verification:
- Static checks confirm the cache-busted assets and analytics layout selectors are present.

## 2026-07-19 — Phase 11 Milestone 4: Exports and Recommendations

Implemented:
- Added deterministic recommendation generation from score, hint, trace, and topic activity.
- Added authenticated interview and execution history endpoints under `/analytics/me/interviews` and `/analytics/me/executions`.
- Added authenticated JSON and CSV exports at `/analytics/me/export?format=json|csv` with download headers.
- Added Analytics UI controls for JSON/CSV downloads and a coaching-signals panel driven by the API response.
- Added regression coverage for recommendations, history data, JSON payloads, and CSV rows.

Verification:
- Backend smoke test passes for a multi-event interview, hint, trace, and execution sequence.
- Application compilation, main-app route registration, and frontend static checks pass.
- Full pytest/TestClient and JavaScript runtime checks remain blocked because this virtualenv lacks `pytest`/`httpx` and the shell lacks `node`.

## 2026-07-19 — Verification Tooling and Tracer Fix

Implemented:
- Installed the requested `pytest`, `httpx`, and Node.js tooling externally.
- Fixed Python tracer import validation so disallowed imports raise a validation error before the worker starts, while runtime execution errors remain trace events.

Verification:
- Full test suite passes: 37 passed.
- Frontend JavaScript syntax check passes with `node --check app/frontend/app.js`.

## 2026-07-19 — Trace Error Messaging Fix

Implemented:
- Updated the trace UI to parse API error details and distinguish rejected code from an unreachable API.
- Added cache busting for the updated frontend script.
- Added an API regression test for rejected imports.

Verification:
- Full test suite passes: 38 passed.
- Frontend JavaScript syntax check passes with `node --check app/frontend/app.js`.
