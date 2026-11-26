# CRI — Controlled Recursive Intelligence

**Internal private project. Pre-GitHub engineering snapshot; not production-ready.** Core invariant: capabilities may increase; authority may not.

## Included implementation

- FastAPI control-plane prototype with bearer protection on sensitive routes.
- Local hash-chained JSONL audit and `cri-audit verify` CLI.
- HMAC-signed expiring one-time approvals with SQLite nonce replay protection.
- Deny-by-default role/scope policy prototype and child-scope intersection.
- Docker sandbox invocation with restrictive flags and fail-closed Docker health preflight.
- Six bounded agent role implementations, AgentFactory, ToolGateway, and in-process asynchronous DAG orchestration.
- React/TypeScript/Vite dashboard shell with 11 navigation areas; only Overview currently reads live backend status. Other pages explicitly identify missing live endpoints/actions.
- Private GitHub Actions workflows and test Compose topology.

## Known limitations

PostgreSQL/Redis/pgvector are not connected to application repositories. OPA is not the runtime policy authority. Audit is not WORM. Kill is a local file latch, not an independent watchdog. JWT/session auth, rate limiting, CSRF and multi-user RBAC are absent. There is no complete autonomous LLM worker system or full 16-state self-improvement pipeline. Docker and GitHub Actions have not been run in this environment. Dashboard feature pages are incomplete. See `STATUS.md`, `AUDIT_REPORT.md`, `TEST_REPORT.md`, and `docs/BLOCKERS.md`.

## Requirements

- Python 3.11+
- Docker Engine + Compose plugin for container execution and Compose demo
- Node.js 22+ and npm for dashboard build
- Supported Linux host; Android PRoot is not a security boundary

## Local setup

```sh
cp .env.example .env
# Set independent random values for CRI_ADMIN_TOKEN and CRI_APPROVAL_SECRET (32+ bytes).
python -m pip install -e 'backend[test]'
make test
make audit
cd dashboard && npm install && npm run lint && npm test -- --run && npm run build
cd ..
make up
```

`make e2e` is a Compose smoke test, not full distributed E2E. `make kill` requires a running API and curl. `make reset` removes Compose volumes.

## GitHub Actions from a phone

Use `docs/GITHUB_ACTIONS_GUIDE.md`. Add the required private repository secrets and run `CRI Internal CI` or `CRI Manual Docker Demo` from the Actions tab. The workflow is configured but has not yet been executed. Green health checks do not prove backend database integration.

## Security and operations

Read `docs/SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/OPERATIONS.md`, `docs/CI.md`, and `docs/MANUAL_TEST_PLAN.md`. Do not expose this prototype to untrusted networks or run untrusted code outside the fail-closed sandbox.
