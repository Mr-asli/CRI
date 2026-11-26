#!/usr/bin/env sh
# Internal local-data backup only; does not back up external services.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DATA_DIR="${CRI_DATA_DIR:-$ROOT/data}"
BACKUP_DIR="${1:-$ROOT/backups}"
mkdir -p "$BACKUP_DIR"
if [ ! -d "$DATA_DIR" ]; then
  echo "Data directory does not exist: $DATA_DIR" >&2
  exit 1
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/cri-local-data-$stamp.tar.gz"
tar -czf "$out" -C "$DATA_DIR" .
echo "$out"
