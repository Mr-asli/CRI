# CRI Quickstart

Requirements: Linux host, Docker Engine, Docker Compose plugin, Python 3.11+ for local tooling, and a DNS name/TLS proxy for public access.

1. Review `.env.example` and the security/deployment boundaries in `DEPLOY.md`.
2. Run `./install.sh`. It creates a private `.env` with independent local secrets when one does not exist, validates required values, and starts Compose.
3. Run `./healthcheck.sh` to check API and dashboard reachability.
4. Keep API/dashboard ports bound to loopback. Configure the HTTPS reverse proxy before public exposure.
5. Run `make test`, `make coverage`, and `make audit` in a Python environment with `backend[test]` installed.

LLM integration is disabled by default; provider credentials are not required for the control plane.
