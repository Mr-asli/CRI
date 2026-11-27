# CRI implementation status — v1.0 candidate

## Work completed in this package revision

- Replaced the deterministic Developer template with an OpenAI-compatible HTTPS code-generation client. It validates raw Python output and syntax, enforces filename/size limits, and returns drafts only. It refuses to generate when provider configuration is missing or the provider fails. Generated code is not executed or promoted by the LLM client.
- Added Redis TTL storage, bounded list-queue primitives, and agent heartbeat/state primitives. Redis remains optional; when configured, startup connectivity is mandatory and startup fails closed if unavailable.
- Added `REDIS_URL` and `OPA_URL` compatibility aliases while retaining the existing `CRI_*` names.
- Added persistent SQLAlchemy models and repository operations for improvement records and agent state, plus PostgreSQL migration `0003_runtime_state.sql`.
- Added a versioned PostgreSQL migration runner using a dedicated privileged `CRI_MIGRATION_DATABASE_URL`. The container removes that variable before starting Uvicorn. Runtime persistence must use the restricted `cri_app` role.
- Made PostgreSQL Audit replay idempotent by using the event hash as the stable event ID. On startup, local JSONL events are replayed to the configured remote receiver and PostgreSQL. `/api/status` now reports the database Audit count and chain-link validity separately from local Audit validity.
- Added authenticated, short-lived, single-use WebSocket tickets. The browser does not place the admin bearer token in the WebSocket URL.
- Added Railway Dockerfile deployment configuration and documented that Railway services (API, Dashboard, PostgreSQL, Redis, OPA) are provisioned as separate services; Docker Compose remains the local/CI topology.
- Updated environment documentation and added regression tests for Redis queues, agent heartbeat, database persistence, Audit idempotency, LLM response validation, and WebSocket ticket use.

## Local verification performed for this ZIP

- Python tests: **77 passed**.
- Python statement coverage: **85%**, meeting the repository's configured CI floor.
- Python compileall: passed.
- Docker Compose, GitHub Actions, and manual-demo YAML parsing: passed.
- Shell script syntax checks: passed.
- Dashboard dependency installation was attempted but timed out; TypeScript, Vitest, and production build are **not verified**.
- Docker Engine, PostgreSQL/pgvector, Redis, OPA, Railway deployment, Docker sandbox execution, and host-level watchdog operation were **not run in this environment**.

## Not certified as complete / required external gates

- The remote audit forwarder sends HTTPS events but cannot itself guarantee WORM. The receiving service must enforce immutable retention/Object Lock and be independently tested. Its status is reported as configured receiver, not verified WORM.
- The self-improvement state machine still needs production orchestration and trusted evidence collection. Client-supplied booleans are not sufficient proof of sandbox/test/security results; do not enable automatic promotion based on untrusted evidence.
- Improvement and agent-state persistence primitives exist, but the complete multi-worker lifecycle and recovery behavior have not been integrated and verified end-to-end.
- Redis queue primitives are implemented, but a production worker-consumer topology and distributed delivery guarantees require deployment integration and tests.
- The Docker sandbox runs through a local Docker CLI only when an operator supplies a digest-pinned image and an isolated runner. The API service must not mount Docker socket. A dedicated remote sandbox provider is still required for Railway deployments.
- The host watchdog and systemd units require installation by a host administrator on an independent Linux host. Railway does not provide a privileged host-level systemd control plane for the application container.
- The API Kill Switch is an application admission latch; the independent host stop path remains an external host-operator integration.
- Dashboard Build, Vitest, and browser acceptance remain unverified due to npm install timeout.
- The LLM Developer requires `CRI_LLM_BASE_URL`, `CRI_LLM_API_KEY`, and `CRI_LLM_MODEL`; without them it fails closed. Provider output remains untrusted draft code.
- Human approval token signing currently uses an environment-provided HMAC secret. Production key custody, rotation, and approval identity assurance should move to a dedicated KMS/HSM.

**Release classification:** implementation candidate for controlled deployment testing, not certified production-ready. No statement that all capabilities are 100% complete or defect-free is made.
