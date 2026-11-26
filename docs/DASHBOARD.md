# CRI Dashboard — internal status

The React + TypeScript + Vite application now has a responsive navigation shell for 11 areas: Overview, Agents, Tasks, Self-improvement, Approvals, Audit, Security, Memory, Monitoring, Settings, and Kill switch. It polls the public `/api/status` endpoint and displays an explicit disconnected state when the API cannot be reached. It does not invent metrics, task rows, agent activity, audit entries, or approvals.

## Current implementation

- Reusable navigation and status cards, responsive layout, dark/light theme toggle, keyboard-operable buttons, labels and semantic landmarks.
- API client in `src/api.ts`; current live data is limited to `/api/status`.
- Kill Switch is deliberately disabled in the UI because authenticated administrative interaction and a two-step confirmation flow have not been implemented there.
- The remaining ten secondary pages are navigation placeholders that explicitly state their data endpoints/actions are not implemented. They are not complete feature pages.

## Local commands

```sh
cd dashboard
npm install
npm run lint
npm test -- --run
npm run build
```

The local environment could not complete `npm install` due to a package registry timeout. CI is configured to install and run the dashboard checks; until that workflow has run successfully, build and test status is unverified.
