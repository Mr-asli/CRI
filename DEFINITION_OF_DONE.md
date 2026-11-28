# CRI Definition of Done

A change is complete only when all applicable conditions below are evidenced:

1. Implementation is production-oriented, typed, bounded, and contains no new TODO, placeholder, or stub.
2. Authorization is enforced outside model instructions; capability growth never changes authority.
3. Security-sensitive decisions fail closed and emit auditable allow/deny events without logging secrets.
4. Unit tests cover new behavior and each fixed defect has a regression test.
5. Integration/E2E tests exercise the real service boundary where infrastructure is available.
6. Python compilation, test suite, coverage gate, dashboard lint/test/build, shell syntax, YAML/Compose validation, and migration checks pass in CI.
7. Documentation, environment template, deployment/runbook, manifest, and audit reports match the implementation.
8. Secrets are absent from the package; defaults are safe; deployment limitations are explicit.
9. No claim of independent sandboxing, host watchdog, WORM storage, or production readiness is made without external verification.
10. Rollback path and operator approval are documented for changes affecting persisted state or deployment.
11. [x] Quota schema migration, server-side owner bypass, consumption-route enforcement, audit decisions, and quota regression tests are present.
12. [x] API liveness and Prometheus request metrics are present; CPU/RAM/disk snapshots and optional Telegram/SMTP alert delivery are implemented. External collector coverage and real delivery remain deployment checks.
13. [x] Backup archives have SHA-256 checksums, immediate archive validation, retention pruning, and a documented restore drill. A successful real restore remains an operator acceptance test.
14. [x] Startup validates critical secrets, boolean flags, and alert thresholds; Compose passes the corresponding runtime settings.
15. [x] Migration, Compose mounts, environment template, API monitoring routes, and operator documentation are synchronized.
