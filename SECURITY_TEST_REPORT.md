# Security test report — local run

Command: `PYTHONPATH=backend pytest -q`  
Latest result: **30 passed**. Coverage run: `coverage run --branch --source=cri -m pytest -q`; total coverage **88%** (line/branch combined coverage.py metric). Security test modules: `tests/security/test_security_regressions.py`, `tests/test_security.py`, `tests/test_api_security.py`.

| # | Invariant / bypass attempt | Evidence | Status |
|---|---|---|---|
| 1 | Agent cannot raise its own role scopes | `test_role_cannot_request_extra_scope` | Tested locally |
| 2 | Child cannot receive more than parent | `test_child_permissions_are_intersection_of_parent_and_role`, `test_agent_factory_child_is_intersection` | Tested locally |
| 3 | Unknown role/action denied | `test_policy_deny_by_default_for_unknown_action` | Tested locally |
| 4 | Agent cannot invoke unknown tool | ToolGateway unknown-tool branch implemented; dedicated edge test pending | Partial |
| 5 | Agent cannot access out-of-scope resource | `test_gateway_checks_kill_policy_and_resource` | Tested locally |
| 6 | Kill latch blocks workflow | `test_kill_switch_blocks_new_workflow_items`, gateway kill test | Tested locally |
| 7 | Agent cannot disable independent watchdog | Independent watchdog does not exist | Not implemented |
| 8 | Agent cannot alter external policy authority | Runtime OPA authority not connected | Not implemented |
| 9 | Audit event modification detected | `test_audit_detects_modified_event` | Tested locally |
| 10 | Audit middle-record deletion detected | `test_audit_chain_rejects_deleted_middle_record` | Tested locally |
| 11 | Audit cannot be deleted by privileged host | Local file is not WORM | Not proven |
| 12 | Sensitive API routes require admin bearer | `test_sensitive_routes_require_bearer` | Tested locally |
| 13 | Missing admin secret prevents startup | `test_application_refuses_missing_admin_secret` | Tested locally |
| 14 | Approval token cannot be replayed | `test_token_is_bound_to_proposal_and_single_use`, `test_token_replay` | Tested locally |
| 15 | Expired token rejected | `test_expired_approval_token_is_rejected` | Tested locally |
| 16 | Promotion without tested state/token denied | `test_promotion_requires_separate_human_token`, API fail-closed test | Tested locally |
| 17 | Code cannot execute without Docker sandbox | `test_sandbox_absence_fails_closed`, `test_unavailable_sandbox_prevents_approval_token` | Tested locally with unavailable-provider path |
| 18 | Child agent cannot issue human approval token | Agent API has no token issuance tool; human approval endpoint is admin-protected | Partially tested; separation is not a distinct service |

The requested 10 hard restrictions and 8 principles are not all proven end-to-end. This report distinguishes unit-level checks from missing independent infrastructure. No claim of penetration-test certification is made.
