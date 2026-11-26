# CRI v1.0 pre-GitHub — status

**Internal/private development snapshot. Not production-ready.**

## Implemented in this snapshot

- Python control-plane API with bearer authentication on sensitive routes.
- Local hash-chained JSONL audit and verification CLI.
- HMAC-signed, expiring, one-time approval tokens with SQLite nonce replay protection.
- Role/scope policy prototype with child-scope intersection and deny-by-default checks.
- Docker sandbox command with restrictive runtime flags and fail-closed preflight; actual Docker execution has not been tested in this environment.
- Six role-specific agent classes with task lifecycle, bounded behavior, audit integration, and factory enforcement of child scope intersection.
- ToolGateway with identity/policy/resource validation, kill latch check, bounded payload/result checks, and audit event.
- Async DAG orchestrator with dependency validation, bounded concurrency, retry/backoff, timeout and circuit-breaker behavior.
- React/TypeScript/Vite dashboard shell with 11 navigation areas, responsive layout, theme toggle, live status polling and explicit disconnected state.
- Private GitHub Actions workflows, Compose test topology, scripts, and operational documentation.

## Still incomplete / not proven

- Dashboard only has a functional Overview status view. The other ten pages are explicit shells; detailed controls, live charts, approval center, logs, policy management, memory snapshots and independent kill UX are not implemented.
- PostgreSQL/Redis/pgvector services are defined for CI, but application repositories and migrations are not connected to them.
- OPA Rego policy is present as a policy artifact; runtime authorization still uses in-process Python policy.
- Audit is local JSONL, not PostgreSQL/WORM immutable storage.
- Kill switch is a local file latch, not an independent watchdog/controller.
- No distributed persistent Orchestrator queue, version registry, rollback engine, or full autonomous LLM workflow.
- Docker was unavailable locally; Docker sandbox, Compose, and E2E have not been run. GitHub Actions workflows have not yet been executed.
- gVisor/Firecracker require a compatible dedicated runner; Firecracker requires KVM and `/dev/kvm`.
- Python line/branch coverage is below 100%; latest observed total is 88% (coverage.py branch mode).

## How to test on GitHub

Follow `docs/GITHUB_ACTIONS_GUIDE.md`. Configure the required repository secrets, upload the extracted `cri/` contents to a private repository, then run `CRI Internal CI` or `CRI Manual Docker Demo` from Actions. Interpret each job according to `docs/CI.md`; green service health checks do not prove backend persistence integration.

## Release classification

This is `cri-v1.0-pre-github.zip`, a pre-GitHub engineering snapshot. It is not `cri-final-v1.0.zip`, not a completed 13-phase release, and not certified against all 18 acceptance criteria.

## Latest local verification

- `PYTHONPATH=backend pytest -q`: 30 passed.
- Branch-mode coverage.py report: 88% total.
- `python -m compileall -q backend`: passed.
- Shell syntax checks and YAML parsing for both workflows and both Compose files: passed.
- `make test` and `make audit`: passed.
- `make e2e`: blocked by missing Docker after the required-secret guard was satisfied with temporary test-only values.
- `npm install`: timed out; dashboard build remains unverified.
