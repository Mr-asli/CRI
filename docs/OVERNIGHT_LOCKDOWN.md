# Overnight Lockdown — current status and required deployment boundary

## Purpose

Overnight Lockdown is a fail-closed operating mode. It must prevent CRI agents and
workers from continuing or restarting work after the authorized execution window.
The governing rule is: **agents may request work, but cannot grant, extend, or
restore their own execution authority.**

## Implemented in this repository

- The authenticated `/api/kill` endpoint activates a persistent stop latch.
- `ToolGateway` checks the latch before invoking registered tools.
- Workflow proposal creation and testing check the latch.
- Agent-run requests now check the latch before executing an agent.
- `/api/restart` is protected by the administrator Bearer token.
- Docker Compose uses `restart: "no"`; it will not automatically restart this
  API container under Docker's restart policy.
- The dashboard labels the application latch accurately and warns that it does
  not terminate the API process.

## Not implemented / cannot be guaranteed by the application

The current API process owns the file-backed latch. Therefore this is **not an
independent host-level kill switch**. It does not terminate the API process,
stop arbitrary child processes, revoke credentials at an external gateway,
or protect against a compromised host, Docker daemon, administrator token, or
host-level supervisor. The dashboard is not a security boundary.

A real unattended deployment must place the worker execution plane under a
separate host/VM administrator boundary:

1. Run workers under a dedicated unprivileged OS identity, separate from the
   API/dashboard identity.
2. Do not grant that identity access to Docker/Podman sockets, system service
   management, cron, startup directories, deployment credentials, or restart
   APIs.
3. Keep the watchdog and stop controller outside the worker's process and
   credential boundary. A worker must not be able to edit their configuration.
4. At the end of a time-limited execution lease, close task admission, revoke
   the lease, stop the worker service/container from the host controller, and
   verify the process/container is gone.
5. Configure the host service with manual-only restart (`Restart=no`) and do
   not enable boot-time autostart for the worker. The human administrator alone
   can restart it after authentication and review.
6. Send shutdown and restart-attempt events to a separately administered,
   append-only remote audit destination.
7. Test shutdown while a worker is busy, after a host reboot, with the API
   unavailable, and with the worker attempting to spawn child processes.

## Safe deployment status

Until an external host controller, isolated worker service, credential
separation, and independent audit sink are installed and tested, CRI must be
considered a local prototype. Do not leave agent execution enabled unattended.
The current Docker Compose stack binds the API to loopback and has no automatic
container restart policy, but those settings alone do not prove that the host
will never restart it.

## v1.0 host watchdog implementation status

This package now includes `scripts/host-watchdog.py`, `scripts/systemd/cri-watchdog.service`, `scripts/systemd/cri-agents.service`, and root-only `request-host-stop.sh` / `request-host-start.sh` operator scripts. They are deployment templates and have not been run against a real systemd host in this environment.

The API and agents must not be able to write `/var/lib/cri-supervisor/STOP`, run `systemctl`, edit systemd units, or access the host Docker socket. The dashboard/API kill latch is still an application-level latch and does not invoke the privileged host watchdog. Treat host-level lockdown as unverified until the target host installation and stop/restart tests pass.
