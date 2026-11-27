# CRI final code audit — v1.0 package

## Scope

Reviewed backend API/core/agents/orchestration/tools, database adapters/models/migrations, OPA policy client and Rego, Redis adapter, audit forwarder, Docker sandbox, host watchdog/systemd templates, Compose files, CI workflow, dashboard Docker packaging, and test suite.

## Corrections and additions

1. Added SQLAlchemy models and repository layer for tasks, audit events, memory records, and pgvector embeddings.
2. Added PostgreSQL migrations, append-only audit trigger, and separate runtime role grants. The runtime DB role does not receive audit UPDATE/DELETE/TRUNCATE privileges.
3. Connected configured PostgreSQL, Redis, and OPA services to application startup; configured dependency failures fail startup closed. Task and memory operations use the repository when PostgreSQL is configured.
4. Connected OPA decisions to human API access and agent policy checks; OPA outages deny access.
5. Added optional HTTPS remote audit forwarding, idempotent PostgreSQL replay, persisted event timestamps, and database-side recomputation of event hashes.
6. Replaced the deterministic Developer template with an OpenAI-compatible HTTPS code-generation client that validates source and remains draft-only.
7. Added a self-improvement stage machine with evidence gates and one-time signed token validation for promotion.
8. Added host-side systemd watchdog and root-only stop/start operator scripts.
9. Added dashboard Dockerfile and Nginx `/api` reverse proxy; added dashboard service to Compose.
10. Reworked CI to run unit/coverage, PostgreSQL migration/pgvector checks, OPA policy evaluation, Compose E2E, and dashboard checks.

## Verification

- 77 local tests passed.
- 85% backend statement coverage (CI threshold: 85%).
- Python compilation and YAML/shell syntax checks passed.

## Findings / limitations

- No actual Docker, PostgreSQL, Redis, OPA server, npm build, or GitHub Actions execution was available here. The integration jobs are authored but unverified in a real runner.
- Docker sandbox code is present and fail-closed but the API container has no Docker daemon socket by design. A dedicated remote sandbox worker with authenticated, narrowly scoped execution API is still required.
- The host watchdog requires root installation on the target host. It is deliberately not callable by agents or the API. The API `/api/kill` endpoint only sets the application latch; the root host stop script is a separate host-level control path and is not yet connected to the dashboard button.
- The optional remote audit receiver must enforce WORM/append-only retention independently. A hash chain alone is tamper-evident, not immutable against a privileged host administrator.
- The self-improvement state machine now has persistence primitives, but it is not a fully autonomous discovery/model-driven improvement service; evidence must come from trusted services, not client-supplied flags.
- Dashboard source includes authenticated one-time-ticket WebSocket support and configurable API upstream. npm install timed out; visual/browser and npm tests await CI.

## Release decision

**Implementation package ready for GitHub Actions validation; not certified production-ready.** Do not enable unattended agent execution until sandbox isolation, host supervisor installation, external audit retention, secrets management, and full CI are verified.
