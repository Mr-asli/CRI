# Independent host watchdog

The watchdog runs outside the API/agent container and watches a root-owned stop-request file. Install the systemd unit files on a dedicated Linux host after adapting `/opt/cri` and Docker paths:

```sh
sudo install -d -o root -g root -m 0700 /var/lib/cri-supervisor
sudo install -m 0644 scripts/systemd/cri-watchdog.service /etc/systemd/system/
sudo install -m 0644 scripts/systemd/cri-agents.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cri-watchdog.service
sudo systemctl enable --now cri-agents.service
```

Operator stop:

```sh
sudo scripts/request-host-stop.sh
sudo systemctl is-active cri-agents.service
```

Operator restart (explicit human action only):

```sh
sudo scripts/request-host-start.sh
```

The API and agents must run as unprivileged identities and must not have write access to `/var/lib/cri-supervisor`, permission to run `systemctl`, access to the host Docker socket, or permission to modify unit files. Do not mount the supervisor state directory into the API container.

This is a deployable reference configuration, not a verified host deployment. Test stop during active work, process-tree termination, reboot behavior, restart behavior, and state-file ownership on the target host. The current dashboard/API Kill Switch is an application-level latch; it is not wired to the privileged host stop request.
