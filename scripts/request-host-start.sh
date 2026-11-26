#!/usr/bin/env sh
set -eu
STATE_FILE="${CRI_HOST_STOP_FILE:-/var/lib/cri-supervisor/STOP}"
if [ "$(id -u)" -ne 0 ]; then echo "must be run by host administrator" >&2; exit 1; fi
# Explicit human/operator action only. Never expose this script through the agent API.
rm -f "$STATE_FILE"
systemctl start cri-agents.service
systemctl is-active --quiet cri-agents.service
echo "CRI workload started by host administrator."
