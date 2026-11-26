# CRI — Controlled Recursive Intelligence

**Private engineering package v1.0.** Core invariant: capabilities may increase; authority may not.

CRI is a governed multi-agent control-plane prototype. It is not certified for unattended autonomous execution or production use.

## Included implementation

- FastAPI control plane with bearer-authenticated administrative routes.
- SQLAlchemy 2.x persistence models/repositories for tasks, audit events, and memory records; PostgreSQL 16 + pgvector migrations.
- Separate database owner and runtime-role grants; the runtime role cannot update/delete audit rows.
- Redis TTL adapter and configured-service startup checks.
- OPA decision client and Rego policies; decisions fail closed when OPA denies or is unavailable.
- Local hash-chained audit log, PostgreSQL append-only trigger, and optional HTTPS remote audit forwarder.
- HMAC-signed expiring one-time approval tokens with SQLite replay protection.
- Developer draft generator, approval-gated self-improvement state machine, and fail-closed Docker sandbox runner.
- Host-side watchdog/systemd templates with root-only stop/start operator scripts.
- React/TypeScript/Vite responsive dashboard, Nginx API reverse proxy, and dashboard Dockerfile.
- Docker Compose topology for API, dashboard, PostgreSQL/pgvector, Redis, OPA, and database migrations.
- GitHub Actions workflow for backend tests/coverage, infrastructure migration and policy checks, Compose E2E, and dashboard validation.

## Local verification in this package build

- 70 Python tests passed.
- 86% backend statement coverage (CI floor: 85%).
- Python compileall passed.
- Both Compose files and the GitHub Actions workflow parsed as YAML.
- Workflow shell blocks passed `bash -n`.

Docker/Compose, live PostgreSQL, Redis, OPA, npm build, browser acceptance, and GitHub Actions were not executed in this environment. See `TEST_REPORT.md` and `BLOCKERS.md`.

## Requirements

- Python 3.11+
- Docker Engine + Compose plugin
- Node.js 22+ and npm
- Supported Linux host for host-watchdog deployment

## Setup

```sh
cp .env.example .env
# Set independent strong values for CRI_ADMIN_TOKEN, CRI_APPROVAL_SECRET,
# POSTGRES_PASSWORD, CRI_APP_PASSWORD, and REDIS_PASSWORD.
python -m pip install -e 'backend[test]'
make test
make coverage
make audit
```

Start the full stack with `docker compose up --build`. The dashboard is served at `http://127.0.0.1:8080`; the API is bound to `127.0.0.1:8000`. Compose applies PostgreSQL migrations before starting the API. Never expose these ports directly to an untrusted network.

For the CI topology, run `docker compose -f docker-compose.test.yml up -d` and follow `.github/workflows/ci.yml`.

## Security boundaries

- The API container has no host Docker socket. Sandbox execution remains unavailable unless an independently operated, restricted sandbox worker is provided; do not mount `/var/run/docker.sock` into the API.
- The host watchdog is installed and controlled by a host administrator. The API kill endpoint is only an application latch; the host stop script is a separate privileged control path.
- Local hash chains detect modification but do not resist root. Use a separate database owner/runtime identity and an independently administered WORM audit collector.
- Model-driven autonomous code generation, distributed queues, gVisor/Firecracker isolation, full chaos testing, KMS/HSM signing, and end-to-end unattended self-improvement are not production-certified.

Read `STATUS.md`, `AUDIT_REPORT.md`, `TEST_REPORT.md`, `BLOCKERS.md`, `docs/INTEGRATIONS.md`, and `docs/HOST_WATCHDOG.md` before deployment.
