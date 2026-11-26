#!/usr/bin/env sh
set -eu
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
: "${CRI_ADMIN_TOKEN:?Set CRI_ADMIN_TOKEN}"
: "${CRI_APPROVAL_SECRET:?Set CRI_APPROVAL_SECRET}"
mkdir -p artifacts
cleanup() {
  docker compose down --volumes --remove-orphans > artifacts/e2e-cleanup.log 2>&1 || true
}
trap cleanup EXIT INT TERM
docker compose up -d
./scripts/wait-for-healthy.sh api 120
curl --fail --silent --show-error http://127.0.0.1:8000/api/status > artifacts/e2e-status.json
curl --fail --silent --show-error -H "Authorization: Bearer $CRI_ADMIN_TOKEN" http://127.0.0.1:8000/api/audit/verify > artifacts/e2e-audit.json
docker compose ps > artifacts/e2e-services.txt
docker compose logs --no-color > artifacts/e2e-logs.txt 2>&1
