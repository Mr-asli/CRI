# Blockers and verification boundaries

| # | Blocker | Reason | What CI can test | Prerequisite / status |
|---|---|---|---|---|
| 1 | Docker absent in local runtime | No Docker CLI/Engine | Compose startup, API image, smoke E2E, sandbox behavior | GitHub-hosted Ubuntu runner; not yet run |
| 2 | PostgreSQL/Redis/pgvector not connected to application repositories | Current application persistence remains local JSONL/SQLite/in-memory | Current CI only starts services and health-checks them | Implement DB/repository integration and migrations before claiming connected persistence |
| 3 | gVisor/Firecracker | Require compatible host runtime; Firecracker needs KVM and `/dev/kvm` | Fail-Closed behavior only on standard runner | Self-hosted Linux runner with KVM; not available here |
| 4 | ruff/mypy unavailable locally | Not installed and package registry timed out | Workflow installs and runs them | GitHub Actions execution pending |
| 5 | GitHub workflows not executed | No remote repository credentials or Actions execution context | Full configured jobs | User pushes private repository and runs Actions |
| 6 | Full chaos/E2E | Requires Docker and multiple services | Compose smoke path only; no full distributed chaos suite yet | GitHub Docker runner; chaos suite remains future work |
| 7 | Dashboard feature pages incomplete | Local npm install timed out; only shell and Overview live status implemented | CI attempts lint/test/build | Successful npm install and implementation of each feature page |
| 8 | External policy authority | Rego policy file exists, but API still uses in-process Policy | Unit policy tests; OPA integration not configured | OPA service + decision client + integration tests |
| 9 | Independent watchdog / kill control | Current kill latch is local file | Unit/API latch tests | Separate supervisor/control plane |
| 10 | PostgreSQL WORM audit | Current audit is local hash-chained JSONL | Tamper-detection unit tests | External append-only/WORM store |
| 11 | Security branch coverage 100% | Current total branch coverage below 100% | Coverage artifact | Additional test branches and actual infrastructure |

The local environment has no Docker CLI, PostgreSQL, Redis server, OPA, or KVM-backed runtime. The project remains fail-closed when Docker sandbox execution is unavailable. GitHub CI has been prepared but has not been executed, so no GitHub result is claimed.

**gVisor/Firecracker:** real isolation tests are not possible on a standard GitHub Actions runner without the required runtime privileges / KVM. Fail-Closed remains active until a dedicated self-hosted runner is configured. Do not treat PRoot as a security boundary.

## Command verification on this host

- `make test`: passed (30 tests).
- `make audit`: passed (empty local chain valid, count 0).
- `make e2e`: first refused because required `CRI_ADMIN_TOKEN` was not configured; rerun with temporary test secrets reached the script and failed because `docker` is not installed.
- `make up` / `make reset`: not runnable because Docker CLI is absent.
- `make kill`: requires a running API and configured admin token; no Docker-backed API was available.
- Dashboard `npm install`: timed out while contacting package registry; dashboard lint/test/build were not run locally.
