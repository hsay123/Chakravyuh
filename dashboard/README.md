# TrapNet-CRS Dashboard

React frontend for the TrapNet-CRS autonomous cyber response system.

## Development

```bash
npm install
npm run dev
```

Opens at `http://localhost:3000`. Vite proxies API/WebSocket requests to the backend orchestrator at `localhost:8000`.

## Build

```bash
npm run build
```

Output in `dist/`.

## Docker

```bash
docker build -t trapnet-dashboard .
docker run -p 3000:80 trapnet-dashboard
```

The nginx config proxies `/incidents`, `/audit-log`, and `/stream` to the backend orchestrator.

## Architecture

Single-page app, no routing. Connects to the backend orchestrator via:

- **WebSocket** (`/stream`) — live incident updates, decoy events, audit entries
- **REST** (`/incidents`, `/audit-log`) — initial data load and approve/reject actions

Components:

| Component | Purpose |
|---|---|
| Header | Title, LIVE indicator, Audit Log button |
| NetworkMap | Real vs decoy asset visualization |
| PipelineStatus | State machine progress for selected incident |
| DiffViewer | Unified diff from Buttercup patches |
| EventFeed | Scrollable live event log |
| ApproveReject | Operator approval controls |
| RawTerminal | Terminal-style raw event view |
| AuditLog | Modal showing approve/reject history |
