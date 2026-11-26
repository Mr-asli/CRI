#!/usr/bin/env sh
# Destructive local restore; requires explicit confirmation and an empty target.
set -eu
archive="${1:?usage: restore.sh BACKUP.tar.gz}"
: "${CRI_RESTORE_CONFIRM:?Set CRI_RESTORE_CONFIRM=YES after stopping CRI and verifying the backup}"
[ "$CRI_RESTORE_CONFIRM" = YES ] || { echo 'Restore confirmation must be YES' >&2; exit 1; }
[ -f "$archive" ] || { echo "Backup not found: $archive" >&2; exit 1; }
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DATA_DIR="${CRI_DATA_DIR:-$ROOT/data}"
mkdir -p "$DATA_DIR"
if [ -n "$(find "$DATA_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
  echo "Refusing to overwrite non-empty data directory: $DATA_DIR" >&2
  exit 1
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
# Reject absolute paths and parent traversal before extraction.
if tar -tzf "$archive" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  echo 'Unsafe path in backup archive' >&2
  exit 1
fi
tar -xzf "$archive" -C "$TMP"
cp -a "$TMP"/. "$DATA_DIR"/
echo "Restored local data to $DATA_DIR"
