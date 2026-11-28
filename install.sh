#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
command -v docker >/dev/null 2>&1 || { echo 'Docker is required' >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required' >&2; exit 1; }
if [ ! -f .env ]; then
  umask 077
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env'); s=p.read_text()
values={
'CRI_ADMIN_TOKEN':'CRI_ADMIN_TOKEN='+secrets.token_urlsafe(48),
'CRI_APPROVAL_SECRET':'CRI_APPROVAL_SECRET='+secrets.token_urlsafe(48),
'POSTGRES_PASSWORD':'POSTGRES_PASSWORD='+secrets.token_urlsafe(36),
'CRI_APP_PASSWORD':'CRI_APP_PASSWORD='+secrets.token_urlsafe(36),
'REDIS_PASSWORD':'REDIS_PASSWORD='+secrets.token_urlsafe(36),
}
for key,line in values.items():
    import re
    s=re.sub(rf'(?m)^{key}=.*$',line,s)
p.write_text(s)
PY
  chmod 600 .env
  echo 'Created .env with generated local secrets. Review it before deployment.'
fi
set -a
. ./.env
set +a
: "${CRI_ADMIN_TOKEN:?CRI_ADMIN_TOKEN is required}"
: "${CRI_APPROVAL_SECRET:?CRI_APPROVAL_SECRET is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${CRI_APP_PASSWORD:?CRI_APP_PASSWORD is required}"
: "${REDIS_PASSWORD:?REDIS_PASSWORD is required}"
for name in CRI_ADMIN_TOKEN CRI_APPROVAL_SECRET POSTGRES_PASSWORD CRI_APP_PASSWORD REDIS_PASSWORD; do
  eval "value=\${$name}"
  [ "${#value}" -ge 32 ] || { echo "$name must be at least 32 characters" >&2; exit 1; }
done
mkdir -p data backups
chmod 700 data backups
docker compose up -d --build
"$ROOT/healthcheck.sh"
echo 'CRI stack started. Configure HTTPS proxy before exposing it publicly.'
