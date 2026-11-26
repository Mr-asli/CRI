#!/usr/bin/env sh
set -eu
: "${CRI_BASE_URL:=http://127.0.0.1:8000}"
: "${CRI_ADMIN_TOKEN:?Set CRI_ADMIN_TOKEN}"
headers="Authorization: Bearer $CRI_ADMIN_TOKEN"
curl --fail --silent --show-error -X POST -H "$headers" "$CRI_BASE_URL/api/kill"
status="$(curl --fail --silent --show-error "$CRI_BASE_URL/api/status")"
printf '%s\n' "$status" | grep -q 'stopped'
curl --fail --silent --show-error -X POST -H "$headers" "$CRI_BASE_URL/api/restart"
