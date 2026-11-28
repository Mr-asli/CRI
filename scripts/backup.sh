#!/usr/bin/env sh
# Create a verified, retention-managed CRI backup (local data + PostgreSQL dump when available).
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"; cd "$ROOT"
DATA_DIR="${CRI_DATA_DIR:-$ROOT/data}"; BACKUP_DIR="${1:-$ROOT/backups}"; RETENTION="${BACKUP_RETENTION_COUNT:-14}"
case "$RETENTION" in ''|*[!0-9]*) echo 'BACKUP_RETENTION_COUNT must be an integer' >&2; exit 2;; esac
[ "$RETENTION" -ge 1 ] || { echo 'retention must be at least 1' >&2; exit 2; }
mkdir -p "$BACKUP_DIR"; stamp="$(date -u +%Y%m%dT%H%M%SZ)"; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT INT TERM
mkdir -p "$tmp/local-data"; [ ! -d "$DATA_DIR" ] || cp -a "$DATA_DIR"/. "$tmp/local-data"/
if command -v docker >/dev/null 2>&1 && docker compose ps --status running postgres 2>/dev/null | grep -q postgres; then
  docker compose exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U cri_owner -d cri -Fc' > "$tmp/postgres.dump"
  [ -s "$tmp/postgres.dump" ] || { echo "PostgreSQL dump is empty" >&2; exit 1; }
  docker compose exec -T postgres pg_restore --list - < "$tmp/postgres.dump" >/dev/null
else echo 'WARNING: PostgreSQL unavailable; only local data is included.' >&2; fi
archive="$BACKUP_DIR/cri-backup-$stamp.tar.gz"; tar -czf "$archive" -C "$tmp" .
if command -v sha256sum >/dev/null 2>&1; then sha256sum "$archive" > "$archive.sha256"; else shasum -a 256 "$archive" > "$archive.sha256"; fi
# Verify immediately before pruning older backups.
if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$archive.sha256" >/dev/null; else shasum -a 256 -c "$archive.sha256" >/dev/null; fi
tar -tzf "$archive" >/dev/null
count=0
for file in $(ls -1t "$BACKUP_DIR"/cri-backup-*.tar.gz 2>/dev/null || true); do count=$((count+1)); if [ "$count" -gt "$RETENTION" ]; then rm -f "$file" "$file.sha256"; fi; done
printf '%s\n' "$archive"
