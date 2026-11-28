#!/usr/bin/env sh
# Destructive restore; requires explicit operator confirmation and verified checksum.
set -eu
archive="${1:?usage: restore.sh BACKUP.tar.gz}"; : "${CRI_RESTORE_CONFIRM:?Set CRI_RESTORE_CONFIRM=YES}"
[ "$CRI_RESTORE_CONFIRM" = YES ] || { echo 'Restore confirmation must be YES' >&2; exit 1; }
[ -f "$archive" ] && [ -f "$archive.sha256" ] || { echo 'Backup or checksum file missing' >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then sha256sum -c "$archive.sha256"; else shasum -a 256 -c "$archive.sha256"; fi
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"; TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT INT TERM
if tar -tzf "$archive" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then echo 'Unsafe archive path' >&2; exit 1; fi
tar -xzf "$archive" -C "$TMP"
DATA_DIR="${CRI_DATA_DIR:-$ROOT/data}"
if [ -d "$TMP/local-data" ]; then mkdir -p "$DATA_DIR"; cp -a "$TMP/local-data"/. "$DATA_DIR"/; fi
if [ -s "$TMP/postgres.dump" ]; then
  command -v docker >/dev/null 2>&1 || { echo 'Docker is required for database restore' >&2; exit 1; }
  docker compose stop api dashboard
  docker compose exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --clean --if-exists --no-owner -U cri_owner -d cri' < "$TMP/postgres.dump"
  docker compose up -d api dashboard
else echo 'No PostgreSQL dump found; only local data was restored.' >&2; fi
