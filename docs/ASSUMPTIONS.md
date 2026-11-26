# Assumptions and Explicit Limitations

## Current implementation

- The project is a prototype and is not production-ready.
- The six agent roles are labels only; the API truthfully reports `implemented: false`.
- Proposal code is deterministic and hard-coded; no LLM-backed runtime or DAG orchestrator exists.
- Workflow state and memory are process-local.
- Audit is local JSONL with a SHA-256 hash chain; it detects ordinary edits but is not immutable against privileged host access and has no WORM authority.
- Approval signatures use HMAC-SHA256; nonce consumption is persisted in SQLite with a unique constraint.
- Sensitive API routes require a static bearer token from environment; JWT/session, CSRF, rate limiting and per-user RBAC do not exist.
- Compose does not mount the host Docker socket into the API service.
- Sandbox checks Docker CLI/Engine availability and refuses execution when unavailable. Real Docker isolation has not been tested in this workspace.
- Android PRoot is not a substitute for a Linux kernel-backed container/VM isolation boundary.
- PostgreSQL/pgvector, Redis-backed app state, external policy, independent watchdog, React dashboard, WebSockets, telemetry, Prometheus, full CI evidence, SBOM, signed builds and production backup/restore are not implemented.

## Development assumptions

- Completion requires code, tests and observable evidence; documentation alone is not proof.
- Fake sandbox implementations are unit-test fixtures only and cannot establish isolation.
- If infrastructure is unavailable, the affected capability must fail closed and be reported as unverified.
- No public network deployment is acceptable until authentication, authorization, secret management, sandbox isolation and independent audit controls are implemented and tested.
