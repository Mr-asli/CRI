# Test report — CRI final package v1.0

## Local results

| Check | Result |
|---|---:|
| Pytest suite | 70 passed |
| Backend statement coverage | 86% |
| CI coverage floor | 85% |
| Python compileall | Passed |
| docker-compose.yml YAML parse | Passed |
| docker-compose.test.yml YAML parse | Passed |
| .github/workflows/ci.yml YAML parse | Passed |
| GitHub Actions shell block syntax | Passed |

Coverage command:

```sh
PYTHONPATH=backend coverage run --source=cri -m pytest -q
coverage report -m --fail-under=85
```

## Added test areas

- SQLAlchemy SQLite repository behavior: create/update/list task, audit row and memory persistence.
- Database engine/session factory and missing URL fail-closed behavior.
- Redis TTL adapter round-trip and validation using a mock client.
- OPA allow, deny, and unavailable-service fail-closed behavior using mocked HTTP.
- External audit HTTPS requirement and POST behavior using mocked HTTP.
- Developer code draft generation and filename validation.
- Self-improvement evidence gates and one-time signed human approval.
- Host watchdog unit allowlist, stop verification, and active-service failure handling.

## Not executed locally

Docker Engine / Compose, PostgreSQL + pgvector migration, Redis server, OPA server/Rego runtime, dashboard npm install, Vitest, TypeScript build, and Docker image builds were not available in the execution environment. The GitHub Actions workflow contains jobs for these checks, but their results remain pending until the workflow is run in the repository.
