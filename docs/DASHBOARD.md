# CRI dashboard

The React + TypeScript dashboard is a responsive administration UI for desktop,
tablet, and mobile. It includes overview metrics sourced from actual API data,
agent registry, proposal queue, human approvals, audit log, security posture,
project memory, team scopes, self-improvement workflow, monitoring status, and
settings. The emergency control is intentionally labeled as an application stop
latch; it is not represented as a host process kill switch.

Protected API requests use an administrator Bearer token entered on the login
screen. The token is held in `sessionStorage` for the current browser session
and cleared on sign-out. Do not use this dashboard over an untrusted network;
use TLS and a proper identity provider/reverse proxy for remote administration.

The dashboard does not fabricate CPU/RAM, task throughput, agent-running state,
or success-rate charts. Host telemetry and live agent activity require a real
metrics/event collector and are displayed as unavailable until connected.

Run locally:

```bash
cd dashboard
npm install
npm run dev
```

Production build and tests:

```bash
npm run lint
npm run build
npm test -- --run
```
