# TrapNet-CRS Backend Orchestrator

Central hub service that manages incident state, receives events from the correlation engine
and Buttercup CRS, pushes live updates to the dashboard via WebSocket, and exposes the
approve/reject endpoints.

## Running standalone

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or with Docker:

```bash
docker build -t trapnet-backend .
docker run -p 8000:8000 trapnet-backend
```

## API Reference

### Dashboard-facing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/incidents` | List all incidents with current state |
| GET | `/incidents/{id}` | Full incident detail including timeline and diff |
| WS | `/stream` | Live event feed (state changes, audit entries) |
| POST | `/incidents/{id}/approve` | Approve patch — body: `{"approver": "name"}` |
| POST | `/incidents/{id}/reject` | Reject patch — body: `{"approver": "name", "reason": "..."}` |
| GET | `/audit-log` | All approve/reject actions with timestamps |
| GET | `/health` | Health check + active WebSocket count |

### Internal (not exposed to frontend)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/internal/events` | Raw decoy event from correlation engine |
| POST | `/internal/crs-status` | State transition from Buttercup adapter |

## State Machine

```
DETECTED → MATCHED → FUZZING → PATCH_GENERATED → VERIFYING → AWAITING_APPROVAL → APPROVED → DEPLOYED
                                                                            └──▶ REJECTED
```

## Files

- `app/main.py` — FastAPI app, all endpoints, WebSocket broadcast, lifespan init
- `app/models.py` — Pydantic models and state machine definitions
- `app/database.py` — SQLite connection, schema, CRUD operations, audit log
- `app/ws_manager.py` — WebSocket connection manager for broadcasting
- `audit.jsonl` — Append-only audit trail (created at runtime)
- `trapnet.db` — SQLite database file (created at runtime)
