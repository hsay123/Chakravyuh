# ARCHITECTURE — Chakravyuh

## 1. High-Level Diagram (textual)

```
                        ┌─────────────────────────────┐
                        │        DASHBOARD (Web)        │
                        │  network map | event feed |    │
                        │  pipeline status | diff view |  │
                        │  incident report | approve/     │
                        │  reject console                 │
                        └───────────────▲─────────────────┘
                                        │ WebSocket / REST
                        ┌───────────────┴─────────────────┐
                        │         BACKEND ORCHESTRATOR      │
                        │        (FastAPI / Node service)   │
                        └──┬──────────────────────┬─────────┘
              events       │                      │  tasks/status
     ┌────────────────────▼───┐        ┌──────────▼──────────────────┐
     │   DECEPTION LAYER        │        │  SANDBOX TWIN MANAGER          │
     │  Q-Cowrie (adaptive SSH) │        │  (custom, Python service)      │
     │  DataTrap (LLM+dataset)  │        │  1. spin up disposable twin    │
     │  → captures raw payload  │──────▶ │     (same stack as real asset) │
     │  + structured event log  │        │  2. replay exact payload       │
     └───────────────────────────┘        │  3. observe: crash or safe?    │
                                          └──────────┬──────────────────┘
                                                     │ if twin crashes:
                                                     │ payload = proven-bad seed
                                          ┌──────────▼──────────────────┐
                                          │   CRS LAYER (afc-buttercup)    │
                                          │  seeded fuzz → root-cause →    │
                                          │  patch → regression-verify     │
                                          │  runs on Minikube locally      │
                                          └──────────┬──────────────────┘
                                                     │ patch, on approval
                                          ┌──────────▼──────────────────┐
                                          │  Real target codebase          │
                                          │  (re-verified on a FRESH twin  │
                                          │  before being marked deployed) │
                                          └─────────────────────────────────┘
```

**Key shift from a classification-based design:** the Sandbox Twin Manager does not guess which
vulnerability class the attacker was probing for and then run a broad fuzzing campaign hoping to find
something similar. It replays the attacker's *exact* payload against a disposable twin and only
proceeds if that twin actually breaks — deterministic proof of exploitability, not inference.

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

### 2.2 Sandbox Twin Manager (your custom build — the actual innovation)
- Consumes the event stream (Kafka-lite: a Redis stream or simple queue is enough for a hackathon).
- **Asset registry** (a config file, not a database, for hackathon scope):
  ```yaml
  assets:
    - decoy_id: fake-plc-01
      real_asset_id: plc-controller-svc
      real_repo: <path/URL to real target's source>
      twin_image: <container image matching the real asset's stack, built ahead of time>
      twin_network: isolated-sandbox-net   # never bridged to decoy, internet, or real asset
  ```
- On event: look up decoy → real asset's `twin_image`.
- **Spin up a fresh, disposable container/VM from `twin_image`** on an isolated network — this is a
  clone of the real asset's software stack, never the real asset itself, and never network-reachable
  from anything else.
- **Replay the captured raw payload** against the twin exactly as received (same bytes/command/
  request the attacker actually sent to the decoy).
- **Observe the outcome:**
  - Twin stays healthy → log as non-issue, tear down twin, publish `TWIN_SURVIVED` status, done.
  - Twin crashes or is compromised → this is proof, not inference. Publish `TWIN_COMPROMISED` status
    with the crashing payload attached, then call afc-buttercup's task API, passing the payload as a
    **seed input** for its fuzzer rather than starting a cold/blind fuzzing run.
- **Always tear down the twin** after the incident concludes (survived, or patch deployed) — twins
  are single-use and disposable, never left running or reused across incidents.
- Publishes every state transition to the backend so the dashboard can show the full
  Detected → Twin Spawned → Replaying → Compromised/Survived sequence live.

### 2.3 CRS Layer — afc-buttercup
- Deployed locally via Minikube (per their manual setup guide: Docker, kubectl, Helm, Minikube).
- `AZURE_ENABLED=false`, `TAILSCALE_ENABLED=false` for local-only operation.
- Exposes a task API — the Sandbox Twin Manager calls this **only after a twin has actually been
  compromised**, passing the proven-crashing payload as a seed input rather than triggering a blind
  fuzzing campaign. This makes the fuzzing step fast and deterministic instead of exploratory.
- Emits status transitions (seed reproduced → root cause identified → patch generated → regression
  pass) — poll or subscribe to these and forward to the Backend Orchestrator.
- Patch output: a diff + a pass/fail regression result — this is what the dashboard's diff view reads.
- **Final re-proof step:** once a patch is approved, the Backend Orchestrator asks the Sandbox Twin
  Manager to spin up one more fresh twin from the *patched* build and replay the exact original
  payload against it — only if this twin survives is the patch marked "deployed" against the real
  asset. This closes the loop with the same deterministic-proof standard used for detection.

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

1. Attacker hits `fake-plc-01` → Q-Cowrie/DataTrap emits event with the **raw payload captured**.
2. Sandbox Twin Manager looks up `plc-controller-svc`'s twin image, spins up a fresh disposable twin
   on an isolated network.
3. Twin Manager replays the exact captured payload against the twin.
4. **Branch A — twin survives:** logged as non-issue, twin torn down, incident closed. No further
   action, no Buttercup run triggered (this is the common case and should resolve in seconds).
5. **Branch B — twin crashes/compromised:** this is proof. Twin Manager calls afc-buttercup's task
   API with the crashing payload as a seed input.
6. Buttercup reproduces the crash immediately (seeded, not blind), root-causes it, generates a patch,
   runs its regression suite, reports pass/fail.
7. Backend Orchestrator receives Buttercup status updates, pushes to dashboard live.
8. Dashboard shows the diff and the full incident report (attacker source, payload, decoy touched,
   twin crash evidence, patch diff); operator clicks Approve.
9. Backend triggers one more fresh twin spin-up from the *patched* build, replays the original
   payload again — only a survive here allows the patch to be marked Deployed against the real asset.
10. Audit entry written; incident report finalized and routed to the named responsible officer.

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
