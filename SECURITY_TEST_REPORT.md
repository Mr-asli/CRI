# Security test report — CRI final package v1.0

Command: `PYTHONPATH=backend pytest -q`  
Latest local result: **70 passed**. Backend statement coverage: **86%**. The coverage metric is not a penetration-test result and does not prove complete branch coverage.

| Control / invariant | Local evidence | Status |
|---|---|---|
| Agent cannot request scopes outside its role | Policy and factory regression tests | Unit-tested |
| Child scopes are intersected with parent scopes | Factory/policy tests | Unit-tested |
| Unknown roles/actions denied | Policy tests | Unit-tested |
| Tool gateway enforces role, scope and kill latch | Gateway tests | Unit-tested |
| Kill latch blocks new workflow actions | Workflow/API tests | Unit-tested |
| OPA false or unavailable decision is denied | Mocked OPA tests and OPAPolicy test | Unit-tested; live OPA pending CI |
| PostgreSQL audit updates/deletes rejected | Migration trigger + restricted runtime grants | Migration authored; live DB verification pending CI |
| Local audit modification detected | Hash-chain tamper tests | Unit-tested |
| Remote audit forwarding uses HTTPS and bearer auth | Mocked HTTP test | Unit-tested; WORM receiver not provided |
| Admin routes require bearer token | API security tests | Unit-tested |
| Missing admin/approval secret prevents startup | API/lifespan tests | Unit-tested |
| Approval token is one-time and proposal-bound | Token/workflow tests | Unit-tested |
| Self-improvement promotion requires one-time signed human token | State-machine test | Unit-tested |
| Docker unavailable prevents code execution | Sandbox fail-closed tests | Unit-tested; live Docker pending |
| Host watchdog stops only allowlisted unit and verifies inactive state | Mocked systemctl tests | Unit-tested; real host deployment pending |
| Agents cannot modify host stop state or invoke systemctl | No host control API/socket is exposed to agents | Architectural restriction; verify host permissions during deployment |

## Not proven

- No penetration test, host escape test, Docker daemon attack test, real PostgreSQL trigger bypass test, or real systemd watchdog exercise was run here.
- A local hash chain is tamper-evident, not immutable against root. The PostgreSQL trigger protects against the restricted runtime role, not the database owner/superuser.
- The remote audit sink is only a client adapter. WORM guarantees must be provided and tested by the receiver.
- The dashboard kill control is an application latch; host-level shutdown is a separate root-operator path and is not wired to the dashboard.

Do not interpret this report as a security certification or approval for unattended operation.
