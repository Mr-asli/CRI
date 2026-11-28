# CRI Status

**Package status: engineering preview; not approved for production autonomous execution.**

- Core invariant: capabilities may increase; authority/permissions may not.
- Python suite: 99 passed; backend coverage 86% against a 70% gate.
- Python compile and shell syntax checks passed.
- Compose/CI YAML syntax passed; Docker runtime validation was unavailable.
- Install, healthcheck, backup/restore, Caddy example, quickstart, deployment and runbook scaffolding added.
- Dashboard base theme updated to dark navy and document direction set to Persian RTL; npm build/browser acceptance remains unverified.
- LLM generation is disabled by default in the Compose deployment configuration.
- API `/v1` aliases added while `/api` compatibility routes remain.
- Quota system, independently operated sandbox worker, host watchdog installation, WORM audit provisioning, durable queue recovery, trusted self-improvement attestation chain, and monitoring alerts remain blockers.

See `TEST_REPORT.md`, `AUDIT_REPORT.md`, and `BLOCKERS.md` for evidence and release gates.
