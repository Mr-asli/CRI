# Universal LLM Gateway v1

CRI's Developer uses `UniversalLLMGateway`; provider-specific HTTP and response parsing live in adapters. The supported adapters are OpenAI-compatible (including OpenRouter), Gemini `generateContent`, and Anthropic Messages. Provider credentials are read server-side and are never exposed to agents or included in gateway audit details.

## Configuration

Set `CRI_LLM_PROVIDER`, `CRI_LLM_BASE_URL`, `CRI_LLM_API_KEY`, and `CRI_LLM_MODEL`. Supported provider names: `openrouter`, `openai-compatible`, `openai`, `gemini`, `anthropic`. Optional fallback uses `CRI_LLM_FALLBACK_PROVIDER`, `CRI_LLM_FALLBACK_BASE_URL`, `CRI_LLM_FALLBACK_MODEL`, and optionally `CRI_LLM_FALLBACK_API_KEY` (defaults to primary key). Other controls: `CRI_LLM_MAX_TOKENS`, `CRI_LLM_TIMEOUT`, `CRI_LLM_RETRIES`, `CRI_LLM_MAX_COST_USD`, `CRI_LLM_INPUT_COST_PER_MILLION`, `CRI_LLM_OUTPUT_COST_PER_MILLION`.

Changing provider/model is configuration-only when the target implements the selected adapter's protocol. The gateway validates provider names, HTTPS endpoints, numeric limits, and incomplete fallback configuration at startup. An empty `CRI_LLM_PROVIDER` resolves to `openai-compatible`. For Gemini, set the base URL to `https://generativelanguage.googleapis.com/v1beta/models`; for Anthropic use `https://api.anthropic.com/v1`; for OpenRouter use `https://openrouter.ai/api/v1`.

The current adapters do not yet implement a shared canonical tool-call schema. OpenAI-compatible endpoints accept OpenAI-format tools. Gemini rejects non-empty generic `tools` rather than silently dropping them; Anthropic rejects generic OpenAI-format tools rather than forwarding an invalid schema. Do not rely on cross-provider tool calling until provider-native schema translation and tool-result round trips are implemented and tested. Simple text completions and JSON mode are the supported common path.

## Security and behavior

- Gateway configuration and credentials are process configuration, not agent tools. No agent-facing method changes provider, keys, fallback or budget.
- Requests use HTTPS, bounded message counts and message content, configured output-token limits, bounded retries and per-request timeout. Numeric settings are range-checked.
- Retry is exponential and only for adapter-classified transient transport/status errors. Provider failure can trigger the configured fallback.
- Audit events contain provider/model, token counts, actor and error type only; no prompts, completions, headers or keys.
- Developer output is syntax-checked Python draft data. It is not executed, tested, trusted or promoted by this gateway.
- Model registry metadata is operator-maintained metadata, not a live vendor capability guarantee.

## Cost accounting limitation

Cost is computed from provider-reported token usage and configured per-million-token rates. Set both rates to the current provider prices. If either is zero or provider usage is absent, the calculated amount underestimates actual cost; this is not a billing meter. The v1 limiter is process-local and resets on process restart, so it is not a distributed hard spending cap across multiple replicas. This limitation remains unresolved in this patch; do not treat the configured ceiling as a global financial control, and do not scale multiple API workers when relying on it. For a strict global ceiling, implement and test a transactional shared limiter (e.g. Redis/SQL) before scaling workers. A cost ceiling of zero prevents any positive estimated charge.

## Health and fallback limitation

Health state is updated from real request success/failure and exposed as a snapshot; this package does not start a background scheduler or send paid periodic probes. An external scheduler may inspect provider status and call a safe operator-controlled probe. Fallback is sequential and only uses explicitly configured fallback credentials/base URL/model.

## Tests and deployment

Unit tests mock all provider HTTP calls. GitHub Actions runs the Python suites and dashboard build. Live provider, rate-limit, billing, Railway networking and fallback behavior must be verified in deployment. Never commit API keys; use GitHub Actions/Railway secret stores. Rotate any key previously exposed in chat or repository history.

### CI end-to-end boundary

The infrastructure E2E smoke workflow intentionally does not create a task through `POST /api/tasks`, because that route invokes the configured external LLM provider and can fail transiently (for example, HTTP 503) or incur usage charges. Instead, the smoke workflow seeds a task row directly in the isolated CI PostgreSQL database and verifies API read-through, Redis caching, memory persistence, and audit behavior. Provider request/retry/fallback behavior is covered by deterministic mocked gateway unit tests. A live-provider check should be a separate opt-in workflow with its own explicit budget and credentials.
