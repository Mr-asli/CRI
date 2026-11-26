# CRI Architecture — pre-GitHub snapshot

## Components

- `backend/cri/main.py`: FastAPI control plane, bearer authentication, status/agent/task/approval/audit/memory endpoints.
- `backend/cri/core.py`: local Audit hash chain, role/scope Policy, file Kill latch, HMAC one-time Tokens, Docker Sandbox preflight, in-memory Memory and proposal Workflow.
- `backend/cri/agents/`: six bounded role implementations and AgentFactory.
- `backend/cri/orchestration/`: async in-process DAG scheduler with dependency validation, bounded concurrency, retries, backoff, timeout and circuit breaker.
- `backend/cri/tools/`: ToolGateway enforcing identity, policy action, resource allowlist, payload/result limits and audit.
- `dashboard/`: React/TypeScript/Vite responsive control-plane shell; Overview reads live `/api/status`; other sections remain explicitly incomplete shells.
- `infra/policies/roles.rego`: OPA policy artifact; runtime API still uses Python Policy.
- `.github/workflows/`: private CI and manual demo workflows.

## Trust boundaries

Agents are untrusted task processors. They do not receive host shell, Docker socket, unrestricted filesystem, or arbitrary network tools. ToolGateway is the only registered tool invocation path. The API process, local audit file, kill latch, policy and in-memory stores are not independent infrastructure trust domains yet.

## Current data flow

Human admin → Bearer-authenticated FastAPI route → Workflow / AgentFactory → Policy / ToolGateway → bounded handler or Sandbox preflight → result → local audit. Approval promotion requires a tested proposal and one-time HMAC token issued by the human-admin route.

## Missing production components

External OPA decision service, PostgreSQL repositories and migrations, Redis queue/cache, pgvector memory, WORM audit sink, independent watchdog, isolated sandbox runner, durable DAG scheduler, LLM provider adapter, version registry/rollback and fully implemented dashboard pages.
