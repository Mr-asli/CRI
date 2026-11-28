# CRI — Controlled Recursive Intelligence

**Private engineering package v1.0.** Core invariant: capabilities may increase; authority may not.

CRI is a governed multi-agent control-plane prototype. It is not certified for unattended autonomous execution or production use.

## Included implementation

- FastAPI control plane with bearer-authenticated administrative routes.
- SQLAlchemy 2.x persistence models/repositories for tasks, audit events, and memory records; PostgreSQL 16 + pgvector migrations.
- Separate database owner and runtime-role grants; the runtime role cannot update/delete audit rows.
- Redis TTL, bounded queue, and agent-heartbeat primitives with configured-service startup checks.
- OPA decision client and Rego policies; decisions fail closed when OPA denies or is unavailable.
- Local hash-chained audit log, idempotent PostgreSQL replay with recomputable event hashes, append-only trigger, and optional HTTPS audit receiver.
- HMAC-signed expiring one-time approval tokens with SQLite replay protection.
- OpenAI-compatible HTTPS Developer code-generation client that produces syntax-checked, review-only drafts; it fails closed without provider configuration.
- Approval-gated self-improvement state machine with durable repository primitives; promotion evidence still requires trusted external orchestration.
- Host-side watchdog/systemd templates with root-only stop/start operator scripts.
- React/TypeScript/Vite responsive dashboard, Nginx API reverse proxy, and dashboard Dockerfile.
- Docker Compose topology for API, dashboard, PostgreSQL/pgvector, Redis, OPA, and database migrations.
- GitHub Actions workflow for backend tests/coverage, infrastructure migration and policy checks, Compose E2E, and dashboard validation.

## Local verification in this package build

- 112 Python tests passed; backend statement coverage: 85% (see `TEST_REPORT.md`).
- Python compilation, shell syntax, and YAML parsing passed after the quota/monitoring/backup/configuration changes.
- Docker/Compose, live PostgreSQL, Redis, OPA, npm/dashboard build, real alert delivery, and a live database restore were intentionally not executed; these remain server-side acceptance checks.

## Requirements

- Python 3.11+
- Docker Engine + Compose plugin
- Node.js 22+ and npm
- Supported Linux host for host-watchdog deployment

## Setup

See `docs/QUICKSTART.md`, `docs/DEPLOY.md`, and `docs/RUNBOOK.md` for the supported operator workflow.

```sh
cp .env.example .env
# Set independent strong values for CRI_ADMIN_TOKEN, CRI_APPROVAL_SECRET,
# POSTGRES_PASSWORD, CRI_APP_PASSWORD, REDIS_PASSWORD, and LLM provider settings
# if you intend to create code proposals.
python -m pip install -e 'backend[test]'
make test
make coverage
make audit
```

Start the full stack with `docker compose up --build`. The API migration runner in the Railway Docker image requires a privileged `CRI_MIGRATION_DATABASE_URL` and `CRI_APP_PASSWORD`; after migrations it removes the privileged URL from the Uvicorn process environment. For Railway-specific service configuration, read `docs/RAILWAY_DEPLOYMENT.md`. The dashboard is served at `http://127.0.0.1:8080`; the API is bound to `127.0.0.1:8000`. Compose applies PostgreSQL migrations before starting the API. Never expose these ports directly to an untrusted network.

For isolated integration infrastructure, run `docker compose --profile test up -d test-postgres test-redis test-opa`; see `.github/workflows/ci.yml`.

## Security boundaries

- The API container has no host Docker socket. Sandbox execution remains unavailable unless an independently operated, restricted sandbox worker is provided; do not mount `/var/run/docker.sock` into the API.
- The host watchdog is installed and controlled by a host administrator. The API kill endpoint is only an application latch; the host stop script is a separate privileged control path.
- Local hash chains detect modification but do not resist root. Use a separate database owner/runtime identity and an independently administered WORM audit collector.
- Model-driven autonomous code generation, distributed queues, gVisor/Firecracker isolation, full chaos testing, KMS/HSM signing, and end-to-end unattended self-improvement are not production-certified.

Read `STATUS.md`, `AUDIT_REPORT.md`, `TEST_REPORT.md`, `BLOCKERS.md`, `docs/INTEGRATIONS.md`, and `docs/archive/HOST_WATCHDOG.md` before deployment.

## Quota, monitoring, and configuration

Data-driven quota enforcement is provided by `plans`, `quota_users`, `usage`, and `feature_flags` (migration `0005_quota.sql`). It applies only to task creation, agent runs, and memory writes. `QUOTA_ENABLED=false` disables quota checks; `OWNER_BYPASS_QUOTA=true` exempts only the server-configured `CRI_OWNER_USER_ID`, never a client-supplied flag. Plan limits live in the `plans.quotas` JSON document; a JSON null feature limit is unlimited. Decisions are audited. See `docs/RUNBOOK.md` for operator SQL and safe quota changes.

The API exposes `/healthz`, Prometheus metrics at `/metrics` and `/api/metrics`, and authenticated `/api/monitoring` host/dependency snapshots. Telegram and SMTP alert channels are optional and configured only through `.env`; delivery is best-effort and must be tested by the operator. Backup archives have SHA-256 sidecars, immediate integrity checks, configurable retention, and a documented disposable-environment restore drill. See `docs/RUNBOOK.md`.

Startup validates the required admin and approval secrets (minimum 32 bytes) and boolean/threshold configuration, failing closed on invalid values. `.env.example` is the canonical development/production variable template; use separate secret values per environment. The production Compose migration now includes `0005_quota.sql`.
