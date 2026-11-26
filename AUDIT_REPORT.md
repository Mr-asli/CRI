# CRI acceptance audit — pre-GitHub snapshot

Statuses are evidence-based. “Proven locally” means only the specific local test/implementation, not production isolation.

| # | Acceptance area | Status | Evidence / gap | Proof stage |
|---|---|---|---|---|
| 1 | API authentication | Proven locally (limited) | `backend/cri/main.py`; `test_sensitive_routes_require_bearer`; static bearer secret, no JWT/session | Local |
| 2 | No Docker socket in API | Proven by config inspection | `docker-compose.yml`; no socket mount | Local inspection |
| 3 | No default approval key | Proven locally | `Tokens` validates 32+ bytes; startup secret test | Local |
| 4 | Real sandbox isolation | Unproven | Docker flags exist; Docker unavailable, no runtime test | GitHub Docker runner |
| 5 | Fail-Closed without sandbox | Proven locally | `test_sandbox_absence_fails_closed`, `test_unavailable_sandbox_prevents_approval_token` | Local |
| 6 | Independent OPA policy authority | Unproven | `infra/policies/roles.rego` exists; API still in-process Policy | Future integration |
| 7 | RBAC/ABAC resource scope | Partial | role/scope policy and ToolGateway resource gate; no full ABAC attributes | Local + future |
| 8 | Independent immutable audit | Unproven | local JSONL hash chain only; no WORM/Postgres | Future infrastructure |
| 9 | Kill switch independent from agents | Partial | file latch blocks API workflow; no independent watchdog | Future infrastructure |
| 10 | Human approval one-time anti-replay | Proven locally (limited) | HMAC, TTL, SQLite nonce; tests cover replay/expiry | Local |
| 11 | AgentFactory child <= parent | Proven locally for implemented factory | scope intersection test | Local |
| 12 | Six agent role implementations | Partial | six bounded role classes and authenticated run endpoint; no LLM connector/long-running workers | Local |
| 13 | DAG orchestration | Partial | async DAG, concurrency, retry, timeout, breaker; in-process only | Local |
| 14 | ToolGateway mandatory path | Partial | policy/resource/kill/audit checks; only narrow memory tool registered | Local |
| 15 | Self-improvement 16-state lifecycle | Unproven | existing proposal workflow is minimal; no full state machine | Future |
| 16 | PostgreSQL/Redis/pgvector persistence | Unproven | Compose services defined, no app repository/migrations | GitHub + implementation |
| 17 | Professional 11-page dashboard | Partial | 11-area navigation; Overview live status; other pages are shells | GitHub build + future UI work |
| 18 | Complete CI/chaos/E2E/operations | Partial | workflows/scripts/docs exist; Actions not run; E2E is smoke only | GitHub + future |

## A–F audit summary

- **A — Source/config review:** no Docker socket mount; secrets are env-only; workflow secrets referenced through GitHub Secrets. Remaining static bearer auth and local state are documented.
- **B — Identity/policy:** role allowlists and child-scope intersection tested; external OPA authority and full ABAC remain open.
- **C — Audit/approval:** hash chain, HMAC token, expiry and replay checks tested; WORM storage and independent human approval service remain open.
- **D — Sandbox/isolation:** fail-closed absence path tested; actual Docker runtime and seccomp behavior not run locally.
- **E — Agents/orchestration/dashboard:** six agent classes, DAG and ToolGateway have unit tests; distributed workers and detailed dashboard pages remain incomplete.
- **F — Build/test/operations:** 30 Python tests pass; branch-mode coverage 88%; Docker, npm install and GitHub Actions not verified. No clean A–F release gate.

No CRITICAL/MAJOR/MINOR-free final certification is claimed. This is a pre-GitHub engineering snapshot.
