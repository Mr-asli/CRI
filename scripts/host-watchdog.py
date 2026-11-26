#!/usr/bin/env python3
"""Host-side CRI stop supervisor. Run as a dedicated systemd unit, not in API container.
The API/agents must not have permission to control this service or write its state file.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ALLOWED_UNIT = "cri-agents.service"

def stop_host_unit(unit: str, systemctl="/bin/systemctl"):
    if unit != ALLOWED_UNIT: raise ValueError("unit not allowlisted")
    result = subprocess.run([systemctl, "stop", ALLOWED_UNIT], capture_output=True, text=True, timeout=20, check=False)
    if result.returncode: raise RuntimeError(result.stderr.strip() or "systemctl stop failed")
    active = subprocess.run([systemctl, "is-active", ALLOWED_UNIT], capture_output=True, text=True, timeout=5, check=False)
    if active.returncode == 0: raise RuntimeError(f"service still active after stop: {active.stdout.strip()}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file", default="/var/lib/cri-supervisor/STOP")
    parser.add_argument("--unit", default=ALLOWED_UNIT)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if os.geteuid() != 0: raise SystemExit("must run as host supervisor service")
    if args.interval < 0.2 or args.interval > 10: raise SystemExit("interval out of range")
    state = Path(args.state_file)
    while True:
        if state.exists():
            stop_host_unit(args.unit)
            print("CRI_STOP_CONFIRMED", flush=True)
            return 0
        time.sleep(args.interval)

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc: print(f"WATCHDOG_ERROR: {exc}", file=sys.stderr); raise SystemExit(1)
