# Security test report — CRI package

## Local checks

- Python security and regression tests are included in the **70 passing** test suite.
- Backend statement coverage measured at **85%**.
- Secret-pattern scan found no embedded credential literals; matches were environment-variable references in Compose/docs.
- Source package excludes runtime SQLite databases and generated audit state.

## Controls present in source

- Role scopes are deny-by-default and child scopes are intersected with parent scopes.
- Approval tokens are HMAC-signed, time-limited and one-time via durable nonce storage.
- Sandbox runner fails closed without Docker and a SHA-256-pinned image; network disabled, read-only root filesystem, dropped capabilities, no-new-privileges, process/memory/CPU limits.
- Audit JSONL uses a local hash chain; optional remote sink is not equivalent to independently verified WORM retention.
- Host watchdog/systemd templates and root-operator stop/start scripts are supplied, but host-level installation and isolation are not certified here.

## Not verified

Docker runtime isolation, PostgreSQL privilege enforcement, trigger behavior, OPA/Redis integration, remote WORM retention, host watchdog independence, GitHub Actions, key custody/rotation, and human approval operations require deployment testing. Keep CRI in supervised development mode until those gates pass.
