#!/usr/bin/env sh
set -eu
service="${1:?usage: wait-for-healthy.sh SERVICE [TIMEOUT_SECONDS]}"
timeout="${2:-120}"
start="$(date +%s)"
while :; do
  state="$(docker compose --profile test ps --format json "$service" 2>/dev/null || true)"
  if printf '%s' "$state" | grep -Eq '"Health":"healthy"|healthy'; then
    exit 0
  fi
  now="$(date +%s)"
  if [ "$((now-start))" -ge "$timeout" ]; then
    echo "Timed out waiting for $service to become healthy" >&2
    docker compose --profile test logs "$service" >&2 || true
    exit 1
  fi
  sleep 2
done
