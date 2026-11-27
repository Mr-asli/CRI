#!/usr/bin/env sh
set -eu
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
: "${CRI_ADMIN_TOKEN:?Set CRI_ADMIN_TOKEN}"
: "${CRI_APPROVAL_SECRET:?Set CRI_APPROVAL_SECRET}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"
: "${CRI_APP_PASSWORD:?Set CRI_APP_PASSWORD}"
: "${REDIS_PASSWORD:?Set REDIS_PASSWORD}"
: "${CRI_LLM_BASE_URL:?Set CRI_LLM_BASE_URL}"
: "${CRI_LLM_API_KEY:?Set CRI_LLM_API_KEY}"
: "${CRI_LLM_MODEL:?Set CRI_LLM_MODEL}"
mkdir -p artifacts
cleanup() {
  docker compose down --volumes --remove-orphans > artifacts/e2e-cleanup.log 2>&1 || true
}
trap cleanup EXIT INT TERM

docker compose up -d --build
./scripts/wait-for-healthy.sh api 180
./scripts/wait-for-healthy.sh dashboard 120
echo "E2E STEP 1: API status"
curl --fail --silent --show-error http://127.0.0.1:8000/api/status > artifacts/e2e-status.json
echo "E2E STEP 2: Audit verify before"
curl --fail --silent --show-error -H "Authorization: Bearer $CRI_ADMIN_TOKEN" http://127.0.0.1:8000/api/audit/verify > artifacts/e2e-audit-before.json

# Exercise OPA-gated API + PostgreSQL task persistence.
echo "E2E STEP 3: Create task"
TASK_HTTP_STATUS="$(curl --silent --show-error \
  -o artifacts/e2e-task-created.json -w '%{http_code}' \
  -X POST http://127.0.0.1:8000/api/tasks \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"goal":"CI integration smoke proposal"}')"

echo "CREATE TASK HTTP STATUS: $TASK_HTTP_STATUS"
if [ "$TASK_HTTP_STATUS" != "200" ] && [ "$TASK_HTTP_STATUS" != "201" ]; then
  echo "CREATE TASK ERROR BODY:"
  cat artifacts/e2e-task-created.json
  exit 1
fi
TASK_ID="$(python -c 'import json; print(json.load(open("artifacts/e2e-task-created.json"))["id"])')"
echo "E2E STEP 4: List tasks"
curl --fail --silent --show-error -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/tasks > artifacts/e2e-tasks.json
python -c 'import json,sys; rows=json.load(open("artifacts/e2e-tasks.json")); assert any(x["id"] == sys.argv[1] for x in rows)' "$TASK_ID"

# Exercise durable memory and audit writes.
echo "E2E STEP 5: Create memory"
curl --fail --silent --show-error -X POST http://127.0.0.1:8000/api/memory \
  -H "Authorization: Bearer $CRI_ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"kind":"lesson","text":"CI persistence smoke record"}' > artifacts/e2e-memory-created.json
echo "E2E STEP 6: Read memory"
curl --fail --silent --show-error -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/memory > artifacts/e2e-memory.json
grep -q 'CI persistence smoke record' artifacts/e2e-memory.json
echo "E2E STEP 7: Audit verify after"
curl --fail --silent --show-error -H "Authorization: Bearer $CRI_ADMIN_TOKEN" \
  http://127.0.0.1:8000/api/audit/verify > artifacts/e2e-audit-after.json

# Verify that the task/audit rows reached PostgreSQL and the task-list cache reached Redis.
docker compose exec -T postgres psql -U cri_owner -d cri -c "SELECT count(*) FROM tasks WHERE id = '$TASK_ID';" > artifacts/e2e-postgres-task.txt
docker compose exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" EXISTS cri:tasks:list' > artifacts/e2e-redis-cache.txt
docker compose ps > artifacts/e2e-services.txt
docker compose logs --no-color > artifacts/e2e-logs.txt 2>&1
