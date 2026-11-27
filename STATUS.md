# CRI implementation status — Universal LLM Gateway v1 candidate

## Implemented in this package revision

- Added `backend/cri/llm/` with OpenAI-compatible (including OpenRouter), Gemini and Anthropic HTTP adapters; normalized content, usage, model, provider and optional tool-call fields.
- Added server-side gateway configuration, model registry, bounded exponential retry, per-request timeout, configured sequential fallback, observed health state, process-local token-cost accounting, and metadata-only audit events.
- Routed the Developer code-proposal client through the gateway while preserving draft-only validation and no execution/promotion behavior. Existing constructor injection remains available for mocked OpenAI-compatible tests.
- Added Redis URL factory, OPA environment factory, and an S3 Object Lock COMPLIANCE writer alongside the existing HTTPS audit receiver.
- Added gateway adapter/fallback/cost/registry tests and S3 Object Lock mock test.
- Added `docs/LLM_GATEWAY.md` and updated `.env.example`.
- Dashboard source, Dockerfile, Vitest configuration, and CI dashboard build job are retained from the inspected source ZIP.

## Verification performed in the documentation review

- Full Python test suite: **98 passed** (Python 3.13.5).
- Python statement coverage: **86%** in the same run, meeting the repository CI threshold.
- These results are local source-level checks; they do not certify external services or deployment.
- This environment did not run Docker Compose, Railway, live Redis, live OPA, S3 Object Lock, or live LLM-provider calls. Dashboard dependencies/build were not re-run in this revision.

## Important limitations — not certified production-ready

- Cost accounting is process-local and only meaningful when accurate provider token prices are configured. It is not a shared multi-replica billing cap and resets on restart. A durable shared limiter is required before horizontal scaling.
- Health status is updated by actual request outcomes; no background periodic probe scheduler is started.
- Fallback requires explicit fallback base URL and model. API compatibility and feature support differ by provider; all three adapters require live provider verification.
- S3 Object Lock writer submits COMPLIANCE retention requests; bucket Object Lock/versioning, IAM restrictions, retention policy, and immutable-read verification must be provisioned and tested by an administrator. The HTTP receiver cannot prove WORM.
- Redis primitives and OPA client are present, but worker-consumer topology and production policy coverage require deployment verification.
- Host watchdog remains a separately installed host-side stop supervisor; Railway containers cannot provide independent host control.
- No production certification, complete security assurance, or claim that all capabilities are 100% verified is made.
