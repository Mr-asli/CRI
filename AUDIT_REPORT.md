# CRI Security and Integration Audit

## Scope

Source-level review of the supplied `CRI-main (2).zip` package and changes made in this working copy. This report does not claim access to Git history, a production server, a Docker host, cloud credentials, or provider accounts.

## Core invariant

**Capabilities may increase; authority and permissions may not.** Security controls must remain outside agent/model discretion. No agent may raise its own permissions, disable oversight/audit/stop controls, grant elevated authority to children, change infrastructure ownership, bypass network/resource policy, or publish without valid human approval.

## Changes made in this revision

- Archived historical reports, Railway configuration, old Compose test file, systemd unit templates, and `build_cri.sh` under `docs/archive/`; source contents are retained.
- Added `docker-compose.override.yml` with isolated ephemeral PostgreSQL/pgvector, Redis, and OPA test services under the `test` profile. Updated CI to use this topology.
- Added `install.sh`, `healthcheck.sh`, local-plus-PostgreSQL backup/restore scripts, Caddy example, and deployment/quickstart/runbook documentation.
- Changed dashboard base palette to the requested dark navy surfaces and accent; set document language/direction to Persian RTL.
- Added LLM opt-out default in deployment config; Developer refuses generation when `LLM_ENABLED=false`.
- Added `/v1/...` REST aliases while preserving `/api/...` routes and authentication behavior.
- Added Dependabot configuration and pip-audit/npm-audit CI steps.
- Added Definition of Done and prioritized blockers register; consolidated security test report into `TEST_REPORT.md`.

## Verified locally

- Python compileall: passed.
- Python test suite after changes: 99 tests passed (see `TEST_REPORT.md`).
- Compose and GitHub Actions YAML syntax parse: passed with PyYAML.
- Shell syntax: passed for install, healthcheck, operational scripts, and archived build helper.

## Not verified / not production-certified

- Docker Compose startup, PostgreSQL 16 migrations, Redis, OPA runtime, and full service E2E: Docker Engine was not available in this execution environment.
- Dashboard npm install/lint/test/build and npm audit: not yet run in a browser-capable CI environment.
- Quota tables/middleware and user/plan identity model: not implemented; tracked as P0 in `BLOCKERS.md`.
- Independent sandbox worker, host-level watchdog installation/Overnight Lockdown, external WORM/S3 Object Lock configuration, worker queue recovery, trusted self-improvement attestations, monitoring exporters/alerts, and actual HTTPS certificate issuance: not verified or complete.
- API `/v1` aliases are source-level and unit-test verified; a formal OpenAPI compatibility review is still required.

## Archive / Git limitation

The supplied ZIP does not include `.git`. Therefore actual `git mv` operations and commit-history preservation were impossible. Files were moved into `docs/archive/` without deleting their contents. Re-run `git add -A` and review rename detection in the real repository before merging.

## Release decision

**Not approved for production autonomous execution.** The package contains useful deployment scaffolding, but all P0 blockers in `BLOCKERS.md` must be closed with external evidence before public deployment or autonomous code execution.
