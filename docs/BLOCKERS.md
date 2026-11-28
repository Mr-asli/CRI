# CRI deployment blockers and prioritized issues

This file records work that cannot honestly be marked complete from a source-only ZIP review. Priorities are ordered by security and deployment impact.

| Priority | Issue | Current package evidence | Required completion / acceptance evidence |
|---|---|---|---|
| P0 | Data-driven Quota | Implemented in migration 0005 and API middleware for task creation, agent runs, and memory writes; owner identity is server-configured and decisions are audited. | Operator must assign real users to plans and validate policy values on the deployed database. Existing bearer-admin API is not a full multi-tenant identity provider. |
| P0 | Independent sandbox worker | API sandbox runner is fail-closed but no independently operated worker service is deployed. | Separate host/VM or hardened runtime; no Docker socket in API; signed job envelope, resource caps, no network by default, cleanup, independent test attestations. |
| P0 | Host watchdog / Overnight Lockdown | Host watchdog and systemd templates are archived as deployment references; not installed or verified on a real host. | Host administrator installation, root-owned state path, separate operator credentials, hang/violation tests, measured stop latency, recovery drill. |
| P0 | WORM audit | Optional remote/S3 writer code exists; no bucket or external receiver can be proven from ZIP. | Provision Object Lock COMPLIANCE bucket, versioning, retention, deny-delete IAM, separate account, tamper test, and restore evidence. |
| P1 | Durable worker queue / DAG | Orchestration code exists, but multi-process durable worker lifecycle, retries, dead-letter queue, crash recovery and full E2E evidence are incomplete. | Worker consumer service, persistent job state, idempotency, retry/backoff/DLQ, kill propagation, integration and chaos tests. |
| P1 | Self-improvement evidence chain | Workflow and approval primitives exist; trusted sandbox/test/security attestations and complete rollback/promotion transaction are not verified end-to-end. | Bind signed attestations to immutable artifact digests, independent security results, expiring one-time approval, atomic promotion and tested rollback. |
| P1 | Quota and multi-user auth | Current admin bearer model is not a multi-tenant user account system. | Add authenticated user identity and plan assignment before enabling quota; keep login/audit outside consumption quota. |
| P1 | Monitoring and alerts | Request metrics, health endpoint, CPU/RAM/disk snapshots, dependency checks, and optional Telegram/SMTP notification code are implemented; dashboard Monitoring page consumes the endpoint. | Configure and verify alert credentials, real host/container metrics, queue exporter, notification delivery, and service-down alerting on the deployment host. |
| P1 | HTTPS host integration | `Caddyfile.example` and deployment instructions are supplied; HTTPS has not been exercised against a real DNS name. | Install Caddy on host, verify Let's Encrypt issuance/renewal, security headers and reverse proxy routing. |
| P1 | Backup/restore verification | Backup now writes SHA-256 sidecars, verifies archives, and prunes by retention count; restore validates checksum and requires explicit confirmation. | Execute the documented disposable-host restore drill and retain evidence. |
| P1 | Environment validation | Startup validates required secrets, booleans, and monitoring thresholds; Compose passes quota/alert settings. | Verify production `.env` values and profile-specific secrets on target host. |
| P1 | Full Compose E2E | Compose topology and CI test overlay are present; this environment has not run Docker Engine/Compose. | Run workflow on GitHub Actions or Linux Docker host and retain logs/artifacts. |
| P2 | API contract/dashboard | `/v1` aliases preserve `/api` compatibility; browser/mobile acceptance and complete dashboard component library/RTL audit remain. | Run npm ci, lint, Vitest, TypeScript build, browser accessibility and Persian RTL checks. |
| P2 | Supply chain | Python dependencies are pinned; npm lock exists. | Add Dependabot, pip-audit and npm audit gates with a reviewed exception process and immutable CI action pinning. |

## Operational warning

The install script creates local secrets and starts Compose. It does not install a host watchdog, provision a WORM bucket, establish a dedicated sandbox host, or configure DNS/TLS. Do not enable autonomous execution or public exposure until all P0 items and the relevant P1 items are closed with evidence.
