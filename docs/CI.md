# Internal CI status

Workflow: `.github/workflows/ci.yml`; manual Docker demo: `.github/workflows/manual-demo.yml`.

- `lint`: installs and runs Ruff and mypy.
- `unit`: runs Python tests and emits coverage artifacts.
- `integration`: builds the backend image and starts isolated PostgreSQL/pgvector and Redis services with health checks. At present it does **not** prove that the backend uses those services; application repository integration remains outstanding.
- `security`: runs security regression and policy/sandbox fail-closed tests.
- `e2e`: builds and starts the Compose API and performs status/audit smoke checks; this is not the full multi-agent E2E workflow.
- `dashboard`: installs dependencies, type-checks, runs Vitest, and builds the React dashboard. CI result is pending.

GitHub-hosted Ubuntu can test Docker build, Compose, PostgreSQL/pgvector and Redis service health, FastAPI startup, Python unit/security tests, the current software kill latch, local hash-chain verification, and the implemented dashboard shell. It cannot establish gVisor or Firecracker isolation on standard runners. Some high-impact chaos and penetration tests are not yet implemented.

The Docker sandbox is fail-closed: if the Docker CLI/Engine is absent or unhealthy, `Sandbox.run` raises `SandboxUnavailable`; the workflow cannot reach tested/approval state. Docker image caching uses BuildKit `cache-from: type=gha` and `cache-to: type=gha,mode=max`. CI secrets are passed through `${{ secrets.* }}` and validated before use; no secret values are stored in workflow files.
