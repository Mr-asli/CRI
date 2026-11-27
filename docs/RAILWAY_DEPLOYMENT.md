# Railway deployment notes

Railway is a multi-service deployment target. `railway.toml` configures the API service image; it does not provision PostgreSQL, Redis, OPA, or the Dashboard automatically. Create/link those as separate Railway services and provide their private-network connection URLs as variables.

## API service

- Repository root: repository root.
- Config file: `railway.toml`.
- Dockerfile: `backend/Dockerfile`.
- Health check: `/api/status`.
- Attach a persistent volume at `/data` for the local JSONL audit file, nonce database, and kill latch. Back up this volume separately.
- Set `CRI_MIGRATION_DATABASE_URL` to a privileged PostgreSQL connection and `CRI_APP_PASSWORD` to a separate random runtime-role password. The container runs migrations before Uvicorn, then unsets `CRI_MIGRATION_DATABASE_URL` from the process environment.
- Set `CRI_DATABASE_URL` to a connection using the restricted `cri_app` role. Never point the runtime URL at the schema owner.
- Set independent `CRI_ADMIN_TOKEN` and `CRI_APPROVAL_SECRET` values.
- Set `CRI_REDIS_URL` and `CRI_OPA_URL` only after those services are provisioned and reachable. Configured integrations are fail-closed.
- Configure the optional LLM provider only when code-draft generation is required.

## Dashboard service

Deploy `dashboard/` as a separate Docker service using `dashboard/Dockerfile`. The Nginx image substitutes `API_UPSTREAM` into its configuration at container start. Compose sets it to `api:8000`; on Railway set it to the API service private DNS name and port, for example `<api-service>.railway.internal:8000`. Do not expose the admin token in dashboard build variables; operators enter it in the authenticated UI session.

## Sandbox and host supervision

Do not mount the Docker socket into the Railway API service. A Railway application container cannot provide an independently privileged host watchdog or host-level systemd Kill Switch. Use a separate, operator-managed Linux sandbox/supervisor host with an authenticated narrow API, or leave execution disabled. Sandbox execution must remain fail-closed until that provider has been tested.

## WORM audit

`CRI_AUDIT_REMOTE_URL` is an HTTPS event receiver, not an S3 Object Lock implementation. The receiver must authenticate, deduplicate by `Idempotency-Key`, enforce append-only retention, and expose independently verifiable retention evidence. Do not label the remote sink WORM until those properties are verified.
