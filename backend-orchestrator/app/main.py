"""TrapNet-CRS Backend Orchestrator — FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    append_audit,
    approve_incident,
    create_incident,
    find_incident_by_decoy,
    get_incident,
    init_db,
    list_incidents,
    read_audit_log,
    reject_incident,
    transition_incident,
)
from app.models import (
    ApproveRequest,
    AuditEntry,
    IncidentState,
    InternalCrsStatus,
    InternalDecoyEvent,
    RejectRequest,
    WebSocketMessage,
)
from app.ws_manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    init_db()
    logger.info("Backend Orchestrator started")
    yield
    logger.info("Backend Orchestrator shutting down")


app = FastAPI(
    title="TrapNet-CRS Backend Orchestrator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dashboard-facing endpoints
# ---------------------------------------------------------------------------

@app.get("/incidents")
async def get_incidents() -> list[dict]:  # type: ignore[type-arg]
    return [i.model_dump() for i in list_incidents()]


@app.get("/incidents/{incident_id}")
async def get_incident_detail(incident_id: str) -> dict:  # type: ignore[type-arg]
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump()


@app.post("/incidents/{incident_id}/approve")
async def approve(incident_id: str, body: ApproveRequest) -> dict:  # type: ignore[type-arg]
    try:
        incident = approve_incident(incident_id, body.approver)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    audit = AuditEntry(
        incident_id=incident_id,
        action="approve",
        approver=body.approver,
    )
    append_audit(audit)

    await manager.broadcast(WebSocketMessage(event="incident_updated", data=incident.model_dump()))
    await manager.broadcast(WebSocketMessage(event="audit_entry", data=audit.model_dump()))

    return incident.model_dump()


@app.post("/incidents/{incident_id}/reject")
async def reject(incident_id: str, body: RejectRequest) -> dict:  # type: ignore[type-arg]
    try:
        incident = reject_incident(incident_id, body.approver, body.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    audit = AuditEntry(
        incident_id=incident_id,
        action="reject",
        approver=body.approver,
        reason=body.reason,
    )
    append_audit(audit)

    await manager.broadcast(WebSocketMessage(event="incident_updated", data=incident.model_dump()))
    await manager.broadcast(WebSocketMessage(event="audit_entry", data=audit.model_dump()))

    return incident.model_dump()


@app.get("/audit-log")
async def get_audit_log() -> list[dict]:  # type: ignore[type-arg]
    return [e.model_dump() for e in read_audit_log()]


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/stream")
async def websocket_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; ignore any client messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Internal endpoints (correlation engine & Buttercup adapter)
# ---------------------------------------------------------------------------

@app.post("/internal/events")
async def internal_decoy_event(event: InternalDecoyEvent) -> dict:  # type: ignore[type-arg]
    """Receive a raw decoy event from the correlation engine.

    If an active incident already exists for this decoy_id, update it.
    Otherwise, create a new incident in DETECTED state.
    """
    existing = find_incident_by_decoy(event.decoy_id)

    if existing is not None:
        # Feed the event detail into the existing incident's timeline
        await manager.broadcast(
            WebSocketMessage(
                event="decoy_event",
                data={"incident_id": existing.incident_id, **event.model_dump()},
            )
        )
        return {
            "status": "event_received",
            "incident_id": existing.incident_id,
            "action": "appended_to_existing",
        }

    incident = create_incident(
        decoy_id=event.decoy_id,
        real_asset_id="",  # Will be filled by correlation engine in a real flow
        technique=event.technique,
    )

    await manager.broadcast(WebSocketMessage(event="incident_created", data=incident.model_dump()))
    await manager.broadcast(
        WebSocketMessage(
            event="decoy_event",
            data={"incident_id": incident.incident_id, **event.model_dump()},
        )
    )

    return {
        "status": "incident_created",
        "incident_id": incident.incident_id,
    }


@app.post("/internal/crs-status")
async def internal_crs_status(status: InternalCrsStatus) -> dict:  # type: ignore[type-arg]
    """Receive a state transition from the Buttercup CRS adapter."""
    try:
        incident = transition_incident(
            status.incident_id,
            status.state,
            diff=status.diff,
            result=status.result,
            detail=status.detail,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await manager.broadcast(WebSocketMessage(event="incident_updated", data=incident.model_dump()))

    return {"status": "transition_applied", "incident_id": incident.incident_id}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:  # str
    return {"status": "ok", "ws_connections": manager.active_count}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
