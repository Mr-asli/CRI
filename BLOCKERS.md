# CRI deployment blockers and verification gates

| Area | Code in package | Local evidence | Required external verification / remaining work |
|---|---|---|---|
| PostgreSQL / migrations | SQLAlchemy models, migrations 0001–0003, privileged migration runner, restricted runtime role | Repository SQLite tests; migration runner compile check | Run migrations against a disposable PostgreSQL 16 + pgvector instance and confirm role grants/trigger behavior in GitHub Actions and Railway |
| PostgreSQL Audit | Stable hash event ID, idempotent replay, DB chain-link status | SQLite repository idempotency test | Verify live Railway row count, replay after DB outage, and hash chain against actual PostgreSQL rows |
| Redis | TTL, bounded queue, heartbeat/state primitives; startup ping | Mock tests only | Verify Redis TLS/auth, persistence policy, queue consumer, retries, and failover on GitHub Actions/Railway |
| OPA | HTTP client, fail-closed wrapper, Rego policies | Mock tests; YAML parse | Run OPA 1.x policy evaluation and API authorization tests; validate all action names and policy input schemas |
| Remote/WORM Audit | HTTPS forwarder plus S3 Object Lock COMPLIANCE writer | Mock HTTP and S3 client tests | Provision bucket Object Lock/versioning, restrictive IAM, retention and tamper/immutability checks; mock tests do not establish WORM |
| Developer Agent / Universal LLM Gateway | OpenAI-compatible, Gemini and Anthropic adapters; normalized response; bounded retry/timeout; configured fallback; model metadata; process-local cost accounting; metadata-only audit | Mock adapter, fallback, retry, cost and draft validation tests; 98 full-suite tests, 86% coverage | Live provider compatibility, pricing, quota, timeout and fallback verification; durable shared cost cap and periodic health scheduler remain required for multi-replica production |
| Self-improvement | Approval-gated stage machine and persistent SQL primitives | Unit tests for stage/token workflow | Durable orchestration, trusted sandbox/test/security attestations, rejection/rollback, approval UX, and recovery need end-to-end integration |
| Docker Sandbox | Docker CLI runner with digest pinning, no network, read-only rootfs, dropped capabilities and quotas | Fail-closed unit tests only | Run on a dedicated isolated runner; never mount Docker socket into API/agent container; validate cleanup, seccomp and escape resistance |
| Host watchdog / Kill Switch | Host-side script and systemd unit templates | Syntax and mocked tests | Install on an independent Linux host, verify root-owned state path and API/agent cannot signal or alter host unit; Railway app container cannot provide this guarantee |
| Dashboard | React source, REST and one-time-ticket WebSocket client, Nginx proxy, Dockerfile | Source inspection; npm install timed out | GitHub Actions must pass `npm ci`, lint, Vitest, TypeScript build and Docker image build; browser/mobile acceptance |
| Railway | Railway TOML and backend Dockerfile | Config/source inspection only | Configure API, Dashboard, Postgres, Redis and OPA as separate services; set persistent volume and secrets; test health, migrations and rollback |
| CI | Unit, integration, E2E and Dashboard jobs | Python 98 passed; 86% coverage; YAML/shell syntax passed in local review | Push branch and inspect actual GitHub Actions artifacts/logs; configure required CI secrets |

## Required secrets / variables

- `CRI_ADMIN_TOKEN`: independent random value, at least 32 bytes.
- `CRI_APPROVAL_SECRET`: independent random signing secret, at least 32 bytes.
- `CRI_MIGRATION_DATABASE_URL`: privileged schema-owner connection; only required during migration startup and removed before Uvicorn starts.
- `CRI_DATABASE_URL`: restricted `cri_app` runtime connection.
- `CRI_APP_PASSWORD`: independent runtime-role password used by migration runner.
- `CRI_REDIS_URL`: authenticated Redis connection.
- `CRI_OPA_URL`: OPA policy endpoint.
- `CRI_AUDIT_REMOTE_URL` / `CRI_AUDIT_REMOTE_TOKEN`: HTTPS append-only receiver credentials.
- `CRI_LLM_BASE_URL` / `CRI_LLM_API_KEY` / `CRI_LLM_MODEL`: OpenAI-compatible provider configuration.
- The infrastructure E2E smoke script seeds a task directly in PostgreSQL and does not require live LLM-provider credentials. Provider integration must be tested separately with explicit opt-in credentials.
- `CRI_SANDBOX_IMAGE`: operator-approved image pinned by immutable SHA-256 digest.

Do not put real secrets in the ZIP, Git history, screenshots, issue reports, or public repository files. Rotate any secret that has ever been committed to a public repository.

## Non-negotiable deployment boundary

The host watchdog is not independent until installed outside the application host/process boundary by an administrator. The API Kill Switch does not stop the Railway host. No Docker socket may be mounted into the API or agent container. Untrusted code execution and automatic promotion remain disabled until a separately operated sandbox and trusted evidence/approval chain have been verified.
