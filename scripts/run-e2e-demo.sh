#!/usr/bin/env sh
set -eu

export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

: "${CRI_ADMIN_TOKEN:?Set CRI_ADMIN_TOKEN}"
: "${CRI_APPROVAL_SECRET:?Set CRI_APPROVAL_SECRET}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"
: "${CRI_APP_PASSWORD:?Set CRI_APP_PASSWORD}"
: "${REDIS_PASSWORD:?Set REDIS_PASSWORD}"

mkdir -p artifacts

cleanup() {
  docker compose down --volumes --remove-orphans > artifacts/e2e-cleanup.log 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose up -d --build

./scripts/wait-for-healthy.sh api 180
./scripts/wait-for-healthy.sh dashboard 120

curl --fail --silent --show-error \
  http://127.0.0.1:8000/api/status \
  > artifacts/e2e-status.json

curl --fail --silent --show-error \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/audit/verify \
  > artifacts/e2e-audit-before.json

# Seed a task directly in PostgreSQL to avoid a live LLM request.
TASK_ID="$(python -c 'import secrets; print(secrets.token_hex(16))')"

docker compose exec -T postgres psql \
  -v ON_ERROR_STOP=1 \
  -U cri_owner \
  -d cri \
  -c "INSERT INTO tasks (id, goal, status, proposal) VALUES ('$TASK_ID', 'CI persistence smoke task', 'draft_only', '{}'::jsonb);" \
  > artifacts/e2e-task-seed.txt

# Verify task read-through via the API.
curl --fail --silent --show-error \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/tasks \
  > artifacts/e2e-tasks.json

python -c '
import json
import sys
rows = json.load(open("artifacts/e2e-tasks.json"))
assert any(str(x["id"]) == sys.argv[1] for x in rows), "Seeded task not returned by API"
' "$TASK_ID"

# Exercise durable memory and audit writes.
curl --fail --silent --show-error \
  -X POST \
  http://127.0.0.1:8000/api/memory \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"kind":"lesson","text":"CI persistence smoke record"}' \
  > artifacts/e2e-memory-created.json

curl --fail --silent --show-error \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/memory \
  > artifacts/e2e-memory.json

grep -q 'CI persistence smoke record' artifacts/e2e-memory.json

curl --fail --silent --show-error \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/audit/verify \
  > artifacts/e2e-audit-after.json

# Verify PostgreSQL task persistence.
TASK_COUNT="$(
  docker compose exec -T postgres psql -tA \
    -U cri_owner -d cri \
    -c "SELECT count(*) FROM tasks WHERE id = '$TASK_ID';"
)"

echo "$TASK_COUNT" > artifacts/e2e-postgres-task.txt
[ "$TASK_COUNT" -ge 1 ]

# Verify PostgreSQL memory persistence.
MEMORY_COUNT="$(
  docker compose exec -T postgres psql -tA \
    -U cri_owner -d cri \
    -c "SELECT count(*) FROM memory_records WHERE content = 'CI persistence smoke record';"
)"

echo "$MEMORY_COUNT" > artifacts/e2e-postgres-memory.txt
[ "$MEMORY_COUNT" -ge 1 ]

# Verify Redis task-list cache.
REDIS_EXISTS="$(
  docker compose exec -T redis sh -c \
    'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning EXISTS cri:tasks:list'
)"

echo "$REDIS_EXISTS" > artifacts/e2e-redis-cache.txt
[ "$REDIS_EXISTS" = "1" ]

docker compose ps > artifacts/e2e-services.txt
docker compose logs --no-color > artifacts/e2e-logs.txt 2>&1
