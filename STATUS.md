# CRI status — final implementation package v1.0

## Implemented in this package

- SQLAlchemy 2.x models and repository boundaries for tasks, audit events, memory records, and optional pgvector embeddings.
- PostgreSQL 16 + pgvector schema migrations (`0001_initial.sql`, `0002_runtime_role.sql`). The runtime role is separate from the migration/database owner; its audit table grants are INSERT/SELECT only and a database trigger rejects UPDATE/DELETE.
- Redis TTL storage adapter and startup connectivity check when `CRI_REDIS_URL` is configured.
- OPA HTTP decision client, fail-closed behavior, Rego authorization policy, and integration with API admin access and agent policy checks when `CRI_OPA_URL` is configured.
- Optional HTTPS remote audit forwarder. The receiving service must provide independently enforced WORM/append-only retention.
- Deterministic Developer draft generator; generated source is a reviewable template, not an unrestricted code-writing model.
- Self-improvement state machine with security, sandbox, test, comparison, and one-time signed human approval gates.
- Docker CLI sandbox runner remains fail-closed: requires an available Docker Engine and an operator-pinned immutable image digest; no Docker socket is mounted into the API container.
- Host watchdog and systemd unit templates. The host-level stop request is created by a root operator outside the API/agent process. Host-level start is also root-operator-only.
- Responsive React dashboard source, Nginx reverse proxy configuration, and production dashboard Dockerfile.
- Docker Compose topology for API, dashboard, PostgreSQL/pgvector, Redis, OPA, and one-shot migrations.
- GitHub Actions workflow for Python tests/coverage, infrastructure migration checks, OPA policy evaluation, compose E2E, and dashboard typecheck/test/build/container build.

**Required status statement:** «موارد باقی‌مانده در محیط محلی (Docker/DB) نوشته شده‌اند و آماده اجرا در GitHub Actions هستند.»

This statement means the integration code and CI jobs are included. It does **not** mean those infrastructure jobs have already passed: this environment did not execute Docker Compose, PostgreSQL, Redis, OPA, or npm container builds.

## Local verification performed

- Python tests: 70 passed.
- Backend statement coverage: 86% (threshold used in CI: 85%).
- Python compileall: passed.
- YAML parse of both Compose files and CI workflow: passed.
- Shell syntax checks for workflow run blocks: passed.

## Not certified / remaining deployment work

- GitHub Actions has not been run from this environment; repository secrets and a real runner are required.
- Dashboard npm install, Vitest, TypeScript build, and Docker build were not run locally.
- Docker sandbox execution was not run. The API container intentionally has no Docker socket; a dedicated remote sandbox worker/host with a restricted, authenticated execution API is required before enabling untrusted-code execution.
- Host watchdog/systemd units are templates and must be installed and tested on a dedicated Linux host. The current API Kill Switch is an application admission latch; it is not wired to the privileged host stop file. The root operator stop script is the independent host control path.
- A remote audit collector is optional and must be configured with `CRI_AUDIT_REMOTE_URL` and `CRI_AUDIT_REMOTE_TOKEN`; its server-side WORM guarantees require separate verification.
- Human approval is authenticated by a one-time HMAC token in the workflow; production signing-key custody/rotation should move to a dedicated KMS/HSM.
- Full agent autonomy, model-provider integration, continuous self-improvement discovery, distributed queues, chaos tests, and gVisor/Firecracker isolation are not certified as production-ready.

CRI must remain in supervised development mode until these deployment gates are verified.
