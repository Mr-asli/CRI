# Database, cache, policy and audit integrations

## PostgreSQL and pgvector

The API uses SQLAlchemy 2.x through `SQLRepository`. Configure `CRI_DATABASE_URL` with a dedicated runtime role. Use URL-safe/hex-encoded random passwords for the Compose-provided connection string. Apply migrations as the database owner:

```sh
psql "$CRI_DATABASE_URL_OWNER" -v ON_ERROR_STOP=1 -f backend/alembic/versions/0001_initial.sql
psql "$CRI_DATABASE_URL_OWNER" -v ON_ERROR_STOP=1 -v app_password="$CRI_APP_PASSWORD" -f backend/alembic/versions/0002_runtime_role.sql
```

The API startup checks connectivity and that the `tasks` table exists. It does not auto-run migrations. The runtime role receives task/memory DML and audit INSERT/SELECT only. The audit trigger rejects row UPDATE/DELETE. Keep migration-owner credentials out of the API container.

Embeddings use 1536-dimensional pgvector values. An embedding provider is not included; callers must supply validated vectors.

## Redis

Set `CRI_REDIS_URL`. Startup pings Redis and fails closed if it is unavailable. `RedisTTLStore` provides bounded TTL key/value storage for short-lived state.

## OPA

Set `CRI_OPA_URL`, e.g. `http://opa:8181`. The API uses `/v1/data/cri/authz/allow`. A missing, false, malformed, or unavailable decision is denied. Policies are mounted read-only from `infra/policies` in Compose.

## Audit

The local JSONL audit is hash-chained. When PostgreSQL is configured, rows are also inserted into `audit_events`; the runtime role cannot update or delete them. Set `CRI_AUDIT_REMOTE_URL` (HTTPS) and `CRI_AUDIT_REMOTE_TOKEN` to forward each row to an external collector. The collector—not this client—must enforce WORM retention, authenticated append-only writes, backups, and independent monitoring.

A hash chain detects edits but does not make a local file immutable against root. PostgreSQL triggers are not a defense against a database owner/superuser. Use separate owner/runtime identities and an independently administered WORM collector.
