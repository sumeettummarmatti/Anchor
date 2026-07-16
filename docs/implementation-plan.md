# Implementation plan

## Phase 1 — Foundation (complete)

Build the FastAPI/uv project, Compose services, settings, Alembic scaffold, logging, error boundary, and `/health`. Verify through Swagger, `curl`, and pytest. The LLM provider registry defaults to OpenAI `gpt-4o-mini` and exposes Groq, Hugging Face, and LM Studio configuration.

## Phase 2 — Auth and users (complete)

Implemented the user and refresh-token models/migration; register, login, refresh, logout, and `/users/me`; plus Google/GitHub OAuth entry and callback endpoints. API tests cover happy paths, invalid credentials, duplicate registration, revoked/rotated refresh tokens, unauthenticated access, validation, and unconfigured OAuth providers.

## Phase 3 — Projects, files, and sessions (complete)

Implemented user-owned project/file CRUD and session/event ingestion with input-size validation, ownership enforcement, and an in-memory per-session event-batch limit. Swagger can create a project, mutate files, open/end a session, and submit editor event batches.

## Phase 4 — Code execution

Integrate self-hosted Piston behind `ExecutionService`, persist execution runs, and implement run/submit endpoints with server-side time limits. Open decision: exact supported language/version matrix from the deployed Piston image.

## Phase 5 — Static analysis

Add isolated, timeout-bound analyzers and structured diagnostics; wire analysis before mentor calls and persist results with executions. Open decision: whether linters run in a dedicated sandbox image or the Piston environment.

## Phase 6 — AI mentor

Add prompt-template builders, static-analysis-grounded chat/hints/error explanations, hint-progression policy, and provider calls solely through `AIService`. Swagger can exercise all mentor flows using mocked providers in default tests.

## Phase 7 — Learner personalization

Add learner profiles, adaptation context, and post-session background updates. Swagger can inspect a profile and observe adapted mentor context.

## Phase 8 — Stuck detection

Compute and persist stuck-score snapshots after events/runs, and expose the on-demand score endpoint.

## Phase 9 — Interview mode

Add grounded question generation, answer feedback, transcript persistence, and completion flow.

## Phase 10 — Visualization

Implement isolated Python trace generation with the language-agnostic steps schema; document stubs for other languages.

## Phase 11 — Analytics

Add append-only analytics events plus summary, weekly, and monthly repository aggregations.

## Phase 12 — Gamification

Add XP ledger, declarative achievement rules, streak updates, and the learner progress endpoint.

## Phase 13 — Problems and instructors

Add instructor-protected problem CRUD, attempts, recommendations, daily problem, roster, cohort performance, and AI summary.

## Phase 14 — Hardening

Add Redis rate limiting, complete endpoint test matrix, live integration-test switch, deployment review, and observability checks.

Each phase ends with an appended `log.md` entry and confirmation before the next phase begins.
