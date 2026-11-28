# CRI Baseline Audit

- Input archive: `/mnt/data/cri.zip`
- Archive SHA-256: `3718a03d90bcc30d8cf5bc097004e46c2db0abfc0b8aee5f3e810f9f9dbed1c3`
- Archive contents: 25 files, approximately 18.9 KB uncompressed.
- Baseline test command: `PYTHONPATH=backend pytest -q`
- Baseline result: **6 passed** (Python 3.13.5 in the inspection environment).
- `make audit`: **failed** with `SyntaxError` caused by escaped quotes in the Makefile command.
- Runtime platform note: this inspection environment is not the user's Android PRoot environment and does not establish Docker isolation.

## Findings

| ID | File(s) | Severity | Finding | Required remediation |
|---|---|---:|---|---|
| B-001 | `backend/cri/main.py` | CRITICAL | All API routes are unauthenticated, including kill, restart, approval, and memory mutation. | Add authenticated human identity, authorization per route, secure session/token lifecycle, CSRF protection where cookie auth is used, and negative API tests. |
| B-002 | `docker-compose.yml`, `backend/cri/main.py`, `backend/cri/core.py` | CRITICAL | The API container mounts the host Docker socket. A compromise of the API process can become host-level control. | Remove direct socket access from the control plane. Use a separately isolated sandbox service/host with a narrow authenticated job API and explicit trust boundary. |
| B-003 | `backend/cri/main.py`, `.env.example` | CRITICAL | The application silently falls back to a known development approval secret if the environment variable is missing. | Fail startup if a strong secret/key is absent; no production fallback. Rotate any exposed development secrets. |
| B-004 | `backend/cri/core.py` | MAJOR | Approval MAC is custom `SHA256(secret || message)`, not standard HMAC; used nonce state is process-local and lost on restart. | Use `hmac` with constant-time comparison and persistent transactional nonce consumption. |
| B-005 | `backend/cri/core.py` | MAJOR | Workflow state and memory are process-local and lost on restart; no durable transaction boundary. | Persist proposals, approvals, events and memory in a database with migrations and transaction-safe state transitions. |
| B-006 | `backend/cri/core.py` | MAJOR | Audit JSONL is not protected against concurrent append races or privileged host rewrite; hash chain is tamper-evident only. | Serialize writes, validate event schema, and move authoritative audit to separately administered append-only/WORM storage. |
| B-007 | `backend/cri/core.py` | MAJOR | Sandbox does not preflight Docker availability/daemon health; missing CLI raises an unclassified exception. | Add explicit preflight, typed `sandbox_unavailable` state, audit event, and fail-closed approval gate. |
| B-008 | `backend/Dockerfile`, `docker-compose.yml`, `backend/cri/core.py` | CRITICAL | Runtime image does not install Docker CLI, while Sandbox invokes `docker`; daemon socket bind paths from a container may not map to host paths. | Separate control plane and sandbox runner; verify real host path semantics in an integration environment. |
| B-009 | `backend/cri/core.py`, `backend/cri/main.py` | MAJOR | `/api/agents` returns six static idle labels; proposal code is hard-coded; there are no operational agent implementations or orchestrator. | Implement real bounded agents, task state machine, orchestrator and truthful status APIs. |
| B-010 | `backend/cri/main.py`, `backend/cri/core.py` | MAJOR | API has no WebSocket, rate limiting, CORS/CSRF policy, comprehensive Pydantic request models, or consistent error schema. | Add secure API boundary and contract/integration tests. |
| B-011 | `backend/cri/core.py` | MAJOR | Policy is a static in-process role map; there is no external policy authority or resource-level ABAC. Child scopes are checked but the model is not a separate infrastructure service. | Implement independently administered policy enforcement and resource-scoped authorization; test bypass attempts. |
| B-012 | `backend/cri/core.py` | MAJOR | Kill latch is a file flag in the same process/control plane; no independent watchdog or process/container enforcement exists. | Implement a separately supervised stop controller and prove stop behavior under agent/API failure. |
| B-013 | `backend/cri/core.py` | MAJOR | Memory secret detection is a narrow regex heuristic and can be bypassed; no quarantine or persistent versioning. | Treat memory as untrusted data, add structured validation/classification, secret scanning, quarantine, persistence and snapshots. |
| B-014 | `backend/cri/main.py` | MAJOR | Dashboard is embedded static HTML, not React; it displays static agents and lacks approval/version/diff/monitoring workflows. | Build React/TypeScript UI backed by real API and WebSocket state. |
| B-015 | `backend/pyproject.toml`, `docs/DEPENDENCIES.md` | MAJOR | Direct dependencies are pinned, but no complete transitive lock, SBOM, automated CVE scan or CI pipeline exists. | Add reproducible lock, dependency audit, SBOM and CI evidence. |
| B-016 | `Makefile` | MINOR | `make audit` is broken due to escaped single quotes passed literally to Python. | Correct quoting and add a test that invokes the target. |
| B-017 | `build_cri.sh` | MAJOR | ZIP builder recursively includes arbitrary files such as `.env`, local data, `.git`, and virtual environments (only `__pycache__` is excluded). | Use an explicit allowlist or robust exclusions; add archive secret scan and deterministic manifest. |
| B-018 | `tests/test_core.py` | MAJOR | Only six unit tests exist; fake sandbox is used and no API auth, concurrency, persistence, real sandbox, property, chaos, or E2E security tests exist. | Expand test matrix; clearly separate mocks from real infrastructure tests. |
| B-019 | `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/ASSUMPTIONS.md` | MINOR | Documents correctly disclose prototype gaps but do not contain full threat model, trust-boundary analysis, data-flow, deployment hardening, or evidence mapping. | Expand documents and link each requirement to code/tests/evidence. |
| B-020 | `README.md`, `docker-compose.yml` | MAJOR | `make up` is not demonstrated to work end-to-end; runtime image lacks Docker CLI and compose grants socket access. | Provide a reproducible deployment path with a separately isolated sandbox service and validate on supported Linux host. |

## Baseline capability truth table

| Capability | Baseline status |
|---|---|
| Six named agents | Display labels only; not real agents |
| Orchestrator/DAG | Not implemented; deterministic single-step workflow only |
| Policy | Static in-process role map |
| Audit | Local JSONL hash chain; not immutable/WORM |
| Kill switch | Same-process file latch; not independent |
| Sandbox | Docker command attempted; not verified; unavailable in current Android PRoot environment |
| Human authentication | Not implemented |
| Approval | Custom MAC and in-memory nonce; not production-safe |
| Database/Redis/pgvector | Not implemented |
| Memory | In-process list with heuristic regex filter |
| Dashboard | Embedded HTML, static agent display |
| React/WebSocket | Not implemented |
| Monitoring/CI/SBOM | Not implemented |
| Tests | Six unit tests pass; no real infrastructure/security E2E evidence |

## Baseline decision

**Baseline is NOT production-ready and does NOT meet the requested acceptance criteria.** The six passing tests prove only the narrow unit behaviors covered by those tests. No final ZIP may be described as complete until the critical and major findings are remediated and acceptance criteria are supported by evidence.
