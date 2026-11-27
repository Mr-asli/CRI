# Database, cache, policy and audit integrations

## PostgreSQL and pgvector

The API uses SQLAlchemy 2.x through `SQLRepository`. Runtime access must use the restricted `cri_app` role. Migrations 0001–0004 create tasks, audit, memory, improvement, agent-state, and pgvector structures; they also create/refresh the runtime role and append-only Audit privileges.

For Railway, set `CRI_MIGRATION_DATABASE_URL` to a privileged schema-owner connection and `CRI_APP_PASSWORD` to a separate random runtime-role password. The API image runs `backend/scripts/migrate.py` before Uvicorn, records applied migration versions, then unsets both privileged migration variables before launching the API process. `CRI_DATABASE_URL` must use `cri_app`. For Compose, the one-shot `migrate` service applies the SQL files before API startup.

Startup checks the required schema objects and Audit timestamp column. It fails if migrations are missing. Tasks, memory, improvements, agent states and Audit rows use the SQL repository. Audit events are replayed from the local JSONL file with the event hash as an idempotency key. PostgreSQL verification recomputes event hashes using the stored event timestamp and checks predecessor links.

Embeddings use 1536-dimensional pgvector values. An embedding provider is not included; callers must supply validated vectors.

## Redis

Set `CRI_REDIS_URL` (or `REDIS_URL`). Startup pings Redis and fails closed if it is unavailable. `RedisTTLStore` provides TTL cache, bounded list-queue operations, short-lived memory cache and agent heartbeat state. Redis is not the authoritative store for tasks or memory; PostgreSQL is. A distributed worker-consumer deployment and queue delivery guarantees still require integration testing.

## OPA

Set `CRI_OPA_URL` (or `OPA_URL`), e.g. `http://opa:8181`. The API uses `/v1/data/cri/authz/allow`. A missing, false, malformed, or unavailable decision is denied. Policies are mounted read-only from `infra/policies` in Compose. When OPA is configured, startup and protected administrative authorization fail closed.

## Developer provider

Set `CRI_LLM_BASE_URL`, `CRI_LLM_API_KEY`, and `CRI_LLM_MODEL`. The endpoint must use HTTPS and implement the OpenAI-compatible chat-completions response shape. The provider returns a Python source draft; CRI validates bounds and syntax but does not treat the output as trusted. Execution is only possible through a separately hardened sandbox, and promotion remains approval-gated.

## Audit

The local JSONL audit is hash-chained. When PostgreSQL is configured, events are inserted into `audit_events`; the runtime role cannot update, delete, or truncate them. Event IDs are stable hashes, making startup replay idempotent. `CRI_AUDIT_REMOTE_URL` (or `AUDIT_WORM_URL`) and its matching token forward events to an HTTPS receiver. The collector—not this client—must enforce WORM/Object Lock retention, authenticated append-only writes, backups, idempotency, and independent monitoring. A configured receiver is not automatically a verified WORM store.

A hash chain detects edits but does not make a local file immutable against root. PostgreSQL triggers are not a defense against a database owner/superuser. Use separate owner/runtime identities and an independently administered WORM collector.
