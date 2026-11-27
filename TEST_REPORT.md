# Test report — CRI package

## Local results

- Python test suite: **77 passed**.
- Backend statement coverage: **85%** (coverage.py run; exact counts can vary with source changes), meeting the configured 85% threshold.
- Python bytecode compilation: completed successfully.
- YAML parsing: both Compose files and both GitHub Actions workflows passed local YAML parsing; Docker execution itself was not run. Shell syntax checks passed.

## Deferred checks

The following require Docker/GitHub Actions or dependency installation and are not marked as passed:

- PostgreSQL/pgvector, Redis, OPA and Compose integration tests.
- End-to-end workflow using real CI secrets.
- Dashboard npm install, Vitest, TypeScript build and production container build. An npm ci attempt timed out in this environment.
- Docker sandbox execution and host systemd/watchdog deployment tests.

A passing local Python suite is not a production-readiness certification.
