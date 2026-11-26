#!/usr/bin/env sh
set -eu
STATE_FILE="${CRI_HOST_STOP_FILE:-/var/lib/cri-supervisor/STOP}"
if [ "$(id -u)" -ne 0 ]; then echo "must be run by host administrator" >&2; exit 1; fi
install -d -o root -g root -m 0700 "$(dirname "$STATE_FILE")"
printf 'STOP %s\n' "$(date -u +%FT%TZ)" > "${STATE_FILE}.tmp"
chmod 0600 "${STATE_FILE}.tmp"
mv -f "${STATE_FILE}.tmp" "$STATE_FILE"
echo "Stop requested; host watchdog will stop cri-agents.service. Verify with systemctl is-active cri-agents.service."
