# DESIGN — TrapNet-CRS

## 1. Pipeline State Machine

```
DETECTED → MATCHED → FUZZING → PATCH_GENERATED → VERIFYING → AWAITING_APPROVAL → APPROVED → DEPLOYED
                                                                       │
                                                                       └──▶ REJECTED
```

Each incident is an object:
```json
{
  "incident_id": "uuid",
  "decoy_id": "fake-plc-01",
  "real_asset_id": "plc-controller-svc",
  "technique": "buffer_overflow_probe",
  "state": "AWAITING_APPROVAL",
  "timeline": [
    {"state": "DETECTED", "ts": "..."},
    {"state": "MATCHED", "ts": "..."},
    {"state": "FUZZING", "ts": "..."},
    {"state": "PATCH_GENERATED", "ts": "...", "diff": "..."},
    {"state": "VERIFYING", "ts": "...", "result": "pass"}
  ],
  "patch_diff": "...",
  "approver": null
}
```

## 2. API Contracts (Backend Orchestrator)

- `GET /incidents` — list all incidents, current state.
- `GET /incidents/{id}` — full detail incl. timeline and diff.
- `WS /stream` — push new events/state changes to dashboard live.
- `POST /incidents/{id}/approve` — body: `{ "approver": "name/id" }` → triggers shadow-apply + reverify.
- `POST /incidents/{id}/reject` — body: `{ "approver": "name/id", "reason": "..." }`.
- `GET /audit-log` — flat list of all approve/reject actions with timestamps.

Internal (not exposed to frontend directly):
- Correlation Engine → Backend: `POST /internal/events` (raw decoy events).
- Buttercup adapter → Backend: `POST /internal/crs-status` (state transitions from Buttercup).

## 3. Dashboard Layout (wireframe description)

```
┌───────────────────────────────────────────────────────────────────┐
│  TrapNet-CRS                                     [● LIVE]  [Audit] │
├───────────────────────┬───────────────────────────────────────────┤
│  NETWORK MAP           │  PIPELINE STATUS (selected incident)       │
│  ● real-plc            │  DETECTED ✓ MATCHED ✓ FUZZING ✓            │
│  ○ fake-plc  (red=hit)  │  PATCH_GEN ✓ VERIFYING ✓                    │
│  ● real-db              │  [ AWAITING APPROVAL ]                     │
│  ○ fake-db              │  [Approve]   [Reject]                      │
├───────────────────────┴───────────────────────────────────────────┤
│  DIFF VIEW                                                           │
│  - buf[len] = input[i];      (vulnerable)                            │
│  + if (i < MAX_LEN) buf[len] = input[i];   (patched)                 │
├───────────────────────────────────────────────────────────────────┤
│  LIVE EVENT FEED                          │ RAW TERMINAL (optional) │
│  10:42:03 attacker@203.0.113.4 → fake-plc │ $ ssh root@decoy...     │
│  10:42:05 technique: buffer_overflow      │ Password: ******        │
│  10:42:06 → matched real-plc, fuzzing...  │ $ id                    │
└───────────────────────────────────────────┴─────────────────────────┘
```

## 4. Tech Stack Recommendation

| Layer | Choice | Why |
|---|---|---|
| Backend Orchestrator | Python + FastAPI + WebSocket | Fast to build, same language as Buttercup/Correlation Engine glue |
| State storage | SQLite (file-based) | No external DB dependency for a demo |
| Frontend | React + plain CSS or Tailwind | Fast to iterate, no heavy build tooling needed |
| Event transport | Redis stream (or even simple polling if time-constrained) | Simple pub/sub between honeypots, correlation engine, backend |
| Deployment | Docker Compose (honeypots + backend + frontend) + Minikube (Buttercup only) | Buttercup requires k8s; keep everything else lightweight |

## 5. Failure-mode Handling (important for a live demo)

- If Buttercup run takes too long live: pre-run once before stage time and cache the fuzz corpus/
  build artifacts so the live run is a warm re-run, not a cold start.
- If venue network drops: have Q-Cowrie/DataTrap event replay from a **real pre-recorded session**
  (a session you genuinely captured earlier, not synthetic) as a fallback trigger — still "real" data,
  just not live-live.
- Always have a recorded video of one full successful run as an absolute fallback.

## 6. What Judges Should See in Under 5 Minutes

1. Point at network map, explain real vs decoy assets (15s).
2. Trigger/show a live attack hitting a decoy (30s).
3. Dashboard shows correlation → Buttercup kicks off (15s).
4. Fast-forward (pre-warmed) to patch generated — show real diff (60s).
5. Show regression pass proof (20s).
6. Operator clicks Approve live — status flips to Deployed (15s).
7. Close with the "why this matters" line: decoys aren't just alarms, they're triggers for
   self-healing, with a human always in the loop.
