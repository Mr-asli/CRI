# Blockers and external verification requirements

| Area | Code included | Local verification | Remaining gate |
|---|---|---|---|
| PostgreSQL / SQLAlchemy | Models, repository, migrations, runtime role | SQLite unit tests only | Run pgvector migration and API integration job on GitHub Actions |
| Redis | TTL adapter and startup ping | Mock unit tests only | Run Redis integration on GitHub Actions |
| OPA | HTTP client, fail-closed wrapper, Rego policy | Mock unit tests only | Start OPA, evaluate Rego and API decisions in CI |
| Audit immutability | Local hash chain, PostgreSQL append-only trigger, optional HTTPS forwarder | Hash-chain tests; remote sink mocked | Separate DB owner/runtime role, WORM collector and retention test |
| Host watchdog | systemd unit + root-only stop/start scripts | subprocess mocked | Install/test on dedicated Linux host; verify API/agent cannot write state or call systemctl |
| Docker sandbox | Docker CLI runner, digest pinning, no-network/read-only/caps/resource limits | Not executed; fail-closed | Dedicated remote sandbox worker/host; do not mount Docker socket into API |
| Developer | Deterministic source draft template | Unit test compiles generated draft | Replace template with reviewed model/code-generation provider behind policy gateway |
| Self-improvement | Stage machine + signed one-time approval | Unit test | Add durable workflow storage, discovery worker, security review implementation and signed-token issuance UI |
| Dashboard | React source, Nginx proxy, Dockerfile | Not built locally | npm/Vitest/TypeScript/Docker build in CI and browser/device acceptance tests |
| Full CI | Workflow jobs authored | YAML/shell syntax only | Push repository, configure secrets, run Actions and inspect artifacts |

## Required GitHub Actions secrets for full Compose E2E

- `CRI_ADMIN_TOKEN` — at least 32 random bytes.
- `APPROVAL_SIGNING_KEY` — independent random secret, at least 32 bytes.
- `CRI_POSTGRES_PASSWORD` — strong database owner password.
- `CRI_APP_PASSWORD` — separate runtime database password.
- `CRI_REDIS_PASSWORD` — strong Redis password.

Never use the same secret for admin authentication, approval signing, PostgreSQL, and Redis.

## Explicit safety boundary

The host watchdog is an external supervisor template, not a privilege boundary until installed by a host administrator. The API kill endpoint does not have host-level privileges. Do not mount `/var/run/docker.sock` into the API container. Untrusted code execution remains disabled unless a dedicated sandbox host/provider has been independently tested.
