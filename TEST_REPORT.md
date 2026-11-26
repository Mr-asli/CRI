# Test report — pre-GitHub snapshot

## Python tests

Command: `PYTHONPATH=backend pytest -q`  
Result: **30 passed**.

Branch coverage command: `PYTHONPATH=backend coverage run --branch --source=cri -m pytest -q` followed by `coverage report -m`. Result: **88% total coverage** (coverage.py statement/branch metric). 100% target is not met.

| File | Coverage |
|---|---:|
| `backend/cri/__init__.py` | 100% |
| `backend/cri/agents/__init__.py` | 100% |
| `backend/cri/agents/base.py` | 93% |
| `backend/cri/agents/factory.py` | 89% |
| `backend/cri/cli.py` | 82% |
| `backend/cri/core.py` | 87% |
| `backend/cri/main.py` | 85% |
| `backend/cri/orchestration/__init__.py` | 100% |
| `backend/cri/orchestration/dag.py` | 94% |
| `backend/cri/tools/__init__.py` | 100% |
| `backend/cri/tools/gateway.py` | 80% |

## Coverage and limitations

- Python unit/security/API/agent/orchestrator tests run locally and passed.
- Docker Compose, real Docker sandbox, PostgreSQL/Redis/pgvector integration, real chaos, and full E2E were not run because Docker/servers are absent.
- Dashboard npm installation timed out due package registry/network limitation; lint, Vitest, and production build were not run locally.
- GitHub Actions workflows have not been executed.
- gVisor/Firecracker tests require a compatible dedicated runner; Firecracker requires KVM.

Do not interpret local unit tests or mock adapters as proof of infrastructure integration.

## Make target checks

- `make test`: passed, 30 tests.
- `make audit`: passed, local empty audit chain verified (`valid=true`, `count=0`).
- `make e2e`: missing-secret guard behaved as designed; with temporary test-only environment secrets, Docker command failed because Docker is not installed. No E2E pass is claimed.
- `make up`, `make reset`: blocked by absent Docker CLI.
- `make kill`: not run against a live API because Docker-backed API is unavailable.
- Dashboard `npm install`: timed out at package registry; lint, test and build not run locally.
