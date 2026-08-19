# ARCHITECTURE — TrapNet-CRS

## 1. High-Level Diagram (textual)

```
                        ┌─────────────────────────────┐
                        │        DASHBOARD (Web)        │
                        │  network map | event feed |    │
                        │  pipeline status | diff view |  │
                        │  approve/reject console         │
                        └───────────────▲─────────────────┘
                                        │ WebSocket / REST
                        ┌───────────────┴─────────────────┐
                        │         BACKEND ORCHESTRATOR      │
                        │        (FastAPI / Node service)   │
                        └──┬─────────────────────────────┬──┘
              events       │                             │  tasks/status
     ┌────────────────────▼───┐                ┌─────────▼───────────────┐
     │   DECEPTION LAYER        │                │   CRS LAYER               │
     │  Q-Cowrie (adaptive SSH) │                │  afc-buttercup            │
     │  DataTrap (LLM+dataset)  │                │  (fuzz→patch→verify loop) │
     │  → structured event log  │                │  runs on Minikube locally │
     └───────────┬──────────────┘                └─────────┬──────────────┘
                 │                                          │
     ┌───────────▼──────────────┐              ┌────────────▼─────────────┐
     │  CORRELATION ENGINE       │──triggers──▶ │  Target repo (real,       │
     │  (custom, Python service) │              │  self-hosted, vulnerable  │
     │  event → asset mapping →  │              │  sample codebase)         │
     │  decide: fuzz real asset? │              └────────────────────────────┘
     └────────────────────────────┘
```

## 2. Components

### 2.1 Deception Layer
- **Q-Cowrie**: SSH/Telnet honeypot with an RL layer on top of Cowrie so responses adapt to attacker
  behaviour across a session rather than replaying the same fake shell every time.
- **DataTrap (ThalesGroup/dd-honeypot)**: generates realistic protocol/service responses using
  attack datasets + an LLM, used for the decoy PLC/DB/admin-panel layer where Q-Cowrie's SSH focus
  doesn't fit (e.g., fake Modbus/PLC service).
- **Output contract**: both must emit structured JSON events to a shared log/queue:
  ```json
  {
    "timestamp": "...",
    "decoy_id": "fake-plc-01",
    "source_ip": "...",
    "session_id": "...",
    "technique": "buffer_overflow_probe | credential_bruteforce | command_injection | ...",
    "raw_payload": "..."
  }
  ```

### 2.2 Correlation Engine (your custom build — the actual innovation)
- Consumes the event stream (Kafka-lite: a Redis stream or simple queue is enough for a hackathon).
- **Asset registry** (a config file, not a database, for hackathon scope):
  ```yaml
  assets:
    - decoy_id: fake-plc-01
      real_asset_id: plc-controller-svc
      real_repo: <path/URL to real target's source>
      vuln_classes_watched: [buffer_overflow, oob_write]
  ```
- On event: look up decoy → real asset → check if `technique` is in `vuln_classes_watched`.
- If matched: call Buttercup's task API to start a fuzz/patch run against `real_repo`.
- Publishes its own status events to the backend so the dashboard can show the "Matched" step.

### 2.3 CRS Layer — afc-buttercup
- Deployed locally via Minikube (per their manual setup guide: Docker, kubectl, Helm, Minikube).
- `AZURE_ENABLED=false`, `TAILSCALE_ENABLED=false` for local-only operation.
- Exposes a task API — Correlation Engine calls this to submit a target repo for fuzzing.
- Emits status transitions (fuzzing → crash found → patch generated → regression pass) — poll or
  subscribe to these and forward to the Backend Orchestrator.
- Patch output: a diff + a pass/fail regression result — this is what the dashboard's diff view reads.

### 2.4 Backend Orchestrator
- Single service (FastAPI recommended — Python keeps it consistent with Buttercup/Correlation Engine).
- Responsibilities:
  - Ingest events from Correlation Engine and Buttercup.
  - Maintain in-memory (or SQLite, for a hackathon) pipeline state per incident.
  - Push live updates to the dashboard via WebSocket.
  - Expose the approve/reject endpoint; on approve, apply patch to a shadow copy of the target and
    re-trigger the regression suite; mark incident "Deployed" on pass.
  - Maintain an append-only audit log (who approved what, when) — even a flat JSON-lines file is fine.

### 2.5 Dashboard (Frontend)
- Single-page app. Plain React or even vanilla HTML/JS + WebSocket is fine — do not over-engineer.
- Panels: Network Map, Live Event Feed, Pipeline Status (state machine visual), Diff Viewer, Approve
  Console, optional raw terminal tail.

## 3. Data Flow (single incident, end to end)

1. Attacker hits `fake-plc-01` → Q-Cowrie/DataTrap emits event.
2. Correlation Engine matches event to `plc-controller-svc`, technique `buffer_overflow` is watched.
3. Correlation Engine calls Buttercup task API with target repo.
4. Buttercup fuzzes → finds crash → generates patch → runs regression suite → reports pass.
5. Backend Orchestrator receives Buttercup status updates, pushes to dashboard live.
6. Dashboard shows diff; operator clicks Approve.
7. Backend applies patch to shadow copy, re-verifies, marks Deployed, writes audit entry.

## 4. Environments

- **Dev/local**: everything on one laptop — Minikube for Buttercup, Docker Compose for honeypots +
  backend + frontend.
- **Demo/finale**: same setup, ideally on a dedicated demo rig tested offline (no dependency on venue
  wifi except for LLM API calls — have a backup/cached-response mode if API access is uncertain).

## 5. Key Design Constraints (do not violate)

- No auto-deployment of patches without explicit human approval (FR-8 in PRD).
- No dummy/hardcoded events in the demo build — every event on screen must come from a live tool run.
- Keep the vulnerability scope narrow (memory-safety C/C++ bugs) — do not try to generalize to every
  bug class; reliability over breadth for the finale.
