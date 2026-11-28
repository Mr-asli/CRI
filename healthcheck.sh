#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo 'Docker unavailable' >&2; exit 1; }
docker compose ps
for url in "${CRI_API_HEALTH_URL:-http://127.0.0.1:8000/api/status}" "${CRI_DASHBOARD_HEALTH_URL:-http://127.0.0.1:8080/}"; do
  curl --fail --silent --show-error --max-time 5 "$url" >/dev/null
done
printf '%s\n' 'CRI API and dashboard health checks passed.'
