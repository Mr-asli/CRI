# Agent Protocol — current bounded implementation

Agents receive a task identifier and a structured dictionary payload through their `execute` method. Each returns an `AgentResult` containing role, task id, status and structured output; successful results are appended to the in-process agent history. The API exposes authenticated one-shot invocation at `POST /api/agents/{role}/run`.

Implemented roles: `master`, `developer`, `research`, `testing`, `auditor`, and `memory`. They are deterministic role workers, not autonomous LLM agents. Research does not access the public internet; Developer drafts proposals but does not modify repository files; Testing describes a test plan and never bypasses Sandbox; Auditor checks supplied invariant violations; Memory writes only through ToolGateway.

## Mandatory rules

1. Agent identity is created by `Policy`/`AgentFactory`; caller-supplied scopes cannot exceed role scopes.
2. Child scopes are `parent.scopes ∩ child_role_capabilities`.
3. Tool calls must pass through ToolGateway: kill check → registered tool lookup → role/action policy → resource allowlist → payload bounds → handler → result bounds → audit.
4. No shell, Docker socket, arbitrary host file access or unrestricted network tool is registered.
5. Human approval tokens are not exposed as agent tools.
6. Agent output is untrusted data and cannot mutate policy or infrastructure configuration.

## Limitations

Agent history is process-local. There is no durable worker queue, LLM provider integration, cross-process identity, streaming event bus, or distributed task lease. The current API invocation is synchronous and should not be treated as a production worker fleet.
