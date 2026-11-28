# CRI Operations Runbook

## Health

Run `../healthcheck.sh`; inspect `docker compose ps`, `docker compose logs --tail=200`, `/api/status`, and `/api/audit/verify`. A green HTTP status does not prove host watchdog or sandbox independence.

## Stop and start

`docker compose stop api dashboard` stops the application services. The API kill endpoint is an admission latch only. Host-level stop/start must be performed by the host administrator using the archived operator scripts after installing the watchdog unit from `docs/archive/systemd/` and reviewing `docs/OVERNIGHT_LOCKDOWN.md`.

## Backup and restore

Run `../scripts/backup.sh`. For restore, stop traffic, verify the archive, then run `CRI_RESTORE_CONFIRM=YES ../scripts/restore.sh <archive>`. Restore is destructive; test on a disposable environment first.

## Incidents

1. Preserve logs and audit data; do not edit or truncate them.
2. Use the independent host stop mechanism if agent execution is active or uncertain.
3. Isolate the affected host/network and rotate potentially exposed credentials.
4. Verify audit chain and database state before restart.
5. Restore only from a verified backup and record operator, time, reason, and recovery evidence.

## Data-driven quotas

Quota enforcement is enabled by `QUOTA_ENABLED=true` and runs only on consumption routes (`POST /api/tasks`, `POST /api/memory`, and `POST /api/agents/{role}/run`, including `/v1` aliases). Login/authentication, status, audit, approvals, and read-only routes are not quota-metered. The database migration `0005_quota.sql` creates `plans`, `quota_users`, `usage`, and `feature_flags`; `quota_users.plan_id` selects the plan and `plans.quotas` is a JSON object keyed by feature. A JSON `null` limit means unlimited. Change a user's plan by updating `quota_users.plan_id`; to remove one feature limit, set that feature's plan quota to JSON null. `QUOTA_ENABLED=false` bypasses all quota checks and should be used only during an approved maintenance window. `OWNER_BYPASS_QUOTA=true` exempts only the trusted server-side identity in `CRI_OWNER_USER_ID` (default `human-admin`); never accept owner status from request data. Every allow/deny decision is appended to the audit log. With a configured production database, unavailable quota persistence fails closed for metered requests.

Example operator SQL (run using the migration/owner account, never the API runtime role):

```sql
UPDATE quota_users SET plan_id = 'free' WHERE id = 'human-admin';
UPDATE plans SET quotas = jsonb_set(quotas, '{task_create}', 'null'::jsonb) WHERE id = 'free';
```

## Monitoring and alerts

`GET /api/monitoring` (admin-authenticated) reports host CPU/RAM/disk snapshots, configured dependency health, agent-heartbeat availability, and threshold alerts. `/metrics` and `/api/metrics` expose Prometheus counters (`cri_http_requests_total`, request duration sum) and `cri_queue_depth`. Host metrics are sampled from the API container/host namespace; container limits and orchestrator-level queue metrics require an external collector. `GET /healthz` is a lightweight liveness check; it is not a readiness proof for every external service.

Configure `ALERT_CPU_PERCENT`, `ALERT_MEMORY_PERCENT`, and `ALERT_DISK_PERCENT` (default 90). Telegram delivery uses `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. SMTP delivery uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `ALERT_EMAIL_FROM`, and `ALERT_EMAIL_TO`. Notifications are best-effort and rate-limited per alert; verify delivery in a controlled environment before relying on it. Alerting is evaluated when an authenticated operator requests `/api/monitoring`.

## Backup verification and recovery drill

Run `BACKUP_RETENTION_COUNT=14 ./scripts/backup.sh` daily; the script creates a gzip archive and adjacent `.sha256` checksum, validates the archive, and prunes older archives while retaining the configured number. Schedule it with the host scheduler, for example a root-owned cron entry:

```cron
17 2 * * * cd /opt/cri && BACKUP_RETENTION_COUNT=14 ./scripts/backup.sh >> /var/log/cri-backup.log 2>&1
```

Manual recovery drill (perform on a disposable test host/database, never against production first):

1. Create a backup and retain both `cri-backup-*.tar.gz` and its `.sha256` file.
2. Copy both files to the test host and verify the checksum with `sha256sum -c <archive>.sha256` (or `shasum -a 256 -c`).
3. Confirm the archive listing with `tar -tzf <archive>` and confirm a PostgreSQL dump is present when a DB backup was expected.
4. Stop application traffic and take a separate snapshot of the test database/data directory.
5. Run `CRI_RESTORE_CONFIRM=YES CRI_DATA_DIR=/path/to/test-data ./scripts/restore.sh <archive>` from the project directory. Restore requires Docker Compose when a PostgreSQL dump is present.
6. Run `./healthcheck.sh`, inspect `docker compose ps`, query `/healthz`, and verify `/api/audit/verify` with an administrator token.
7. Compare representative task, memory, audit, and nonce records with the source snapshot. Record operator, timestamp, archive name, checksum, result, and discrepancies.
8. Discard the disposable test environment only after recording the result. Do not treat a checksum as proof of backup completeness; the restore drill is the completeness test.
