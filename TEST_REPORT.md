# Test report — CRI package

## Local results

- Python test suite: **70 passed**.
- Backend statement coverage: **85%** (1016 statements; 152 missed), meeting the configured 85% threshold.
- Python bytecode compilation: completed successfully.
- YAML parsing: Compose and GitHub Actions configuration were previously validated; Docker execution itself was not run.

## Deferred checks

The following require Docker/GitHub Actions or dependency installation and are not marked as passed:

- PostgreSQL/pgvector, Redis, OPA and Compose integration tests.
- End-to-end workflow using real CI secrets.
- Dashboard npm install, Vitest, TypeScript build and production container build. An npm install attempt did not complete in this environment.
- Docker sandbox execution and host systemd/watchdog deployment tests.

A passing local Python suite is not a production-readiness certification.
