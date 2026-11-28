# CRI Deployment Guide

## Scope and prerequisites

This package deploys the API, dashboard, PostgreSQL 16 with pgvector, Redis, OPA, and migrations through Docker Compose. It does **not** make the API a trusted autonomous execution host. Docker sandbox execution, host watchdog independence, and external WORM audit storage require separately administered infrastructure.

Use a supported Linux host with Docker Engine/Compose, a DNS name, and firewall rules that expose only 80/443. Do not publish the API, PostgreSQL, Redis, or OPA ports directly.

## Install

1. Obtain the release archive and verify its SHA-256 out-of-band.
2. Extract it to a dedicated directory and review `.env.example`.
3. Run `../install.sh`. It generates independent local secrets only when `.env` is absent, uses restrictive permissions, validates secrets, and starts the stack.
4. Run `../healthcheck.sh`.
5. Configure Caddy using `Caddyfile.example`: set `CRI_DOMAIN` to a DNS name pointing to the host, then run Caddy as a separate host service or container. Caddy obtains and renews Let's Encrypt certificates automatically. Do not expose the dashboard/API before TLS and authentication are configured.

## Updates and rollback

Back up PostgreSQL and local audit/nonce data with `../scripts/backup.sh`. Pull/review the new package, preserve the previous release directory, apply migrations via Compose, and verify health/audit before switching traffic. Roll back by restoring the prior package and a verified backup; database schema rollback is not automatic.

## Secrets

Generate distinct values for admin token, approval secret, PostgreSQL owner password, runtime DB password, and Redis password. Never commit `.env`. Rotate any credential that has appeared in logs, screenshots, chat, or source control. LLM is disabled by default; configure it only after the control plane is verified.

## External controls required before production autonomy

- Dedicated sandbox worker on a separate host/VM; no Docker socket in API/agent containers.
- Host-admin-installed watchdog and stop/start controls outside application ownership.
- Independently administered S3 Object Lock COMPLIANCE bucket or equivalent WORM receiver, with restrictive IAM and retention verification.
- Trusted test/security attestations and one-time human approval for promotion.

## Environment variables (complete operator list)

Copy `.env.example` to `.env`, restrict it to the deployment operator (`chmod 600 .env`), and set independent random secrets. Startup fails closed if `CRI_ADMIN_TOKEN` or `CRI_APPROVAL_SECRET` is absent or shorter than 32 bytes, or if boolean/threshold values are invalid.

| Variable | Purpose |
|---|---|
| `CRI_ADMIN_TOKEN`, `CRI_APPROVAL_SECRET` | Required API bearer and approval signing secrets (>=32 bytes, independent). |
| `CRI_DATA_DIR`, `CRI_AUDIT_FILE`, `CRI_KILL_FILE`, `CRI_NONCE_DB` | Persistent local state paths. |
| `CRI_MIGRATION_DATABASE_URL`, `CRI_APP_PASSWORD`, `CRI_DATABASE_URL`, `POSTGRES_PASSWORD` | Privileged migration connection, runtime DB password/URL, and Compose owner password. |
| `CRI_REDIS_URL`, `REDIS_PASSWORD`, `CRI_OPA_URL` | Redis and OPA service endpoints/credentials. |
| `QUOTA_ENABLED`, `OWNER_BYPASS_QUOTA`, `CRI_OWNER_USER_ID` | Quota enforcement, trusted owner bypass switch, and server-side owner identity. Do not use client-provided identity for owner status. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional Telegram alert channel. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `ALERT_EMAIL_FROM`, `ALERT_EMAIL_TO` | Optional SMTP alert channel. |
| `ALERT_CPU_PERCENT`, `ALERT_MEMORY_PERCENT`, `ALERT_DISK_PERCENT` | Alert thresholds, each in (0,100]. |
| `BACKUP_RETENTION_COUNT` | Host-side backup retention count (default 14); consumed by `scripts/backup.sh`. |
| `LLM_ENABLED`, `CRI_LLM_*` | Optional LLM gateway; disabled by default. |
| `CRI_AUDIT_REMOTE_URL`, `CRI_AUDIT_REMOTE_TOKEN`, `CRI_AUDIT_S3_BUCKET`, `CRI_AUDIT_S3_RETENTION_DAYS`, `AWS_REGION` | Optional external audit/WORM configuration. |
| `VITE_API_BASE`, `PORT` | Dashboard build-time API base and API listen port. |
| `ALERT_*` | Alert thresholds and recipient configuration as listed above. |

Development and production use the same variable names but different values and services. Use a separate local `.env` for development; never copy production credentials into development or commit either file. The provided `.env.example` is the canonical template for both profiles.
