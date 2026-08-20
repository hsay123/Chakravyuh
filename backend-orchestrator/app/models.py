"""Pydantic models for TrapNet-CRS Backend Orchestrator."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class IncidentState(str, Enum):
    DETECTED = "DETECTED"
    MATCHED = "MATCHED"
    FUZZING = "FUZZING"
    PATCH_GENERATED = "PATCH_GENERATED"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    DEPLOYED = "DEPLOYED"
    REJECTED = "REJECTED"


# Valid state transitions
VALID_TRANSITIONS: dict[IncidentState, list[IncidentState]] = {
    IncidentState.DETECTED: [IncidentState.MATCHED],
    IncidentState.MATCHED: [IncidentState.FUZZING],
    IncidentState.FUZZING: [IncidentState.PATCH_GENERATED],
    IncidentState.PATCH_GENERATED: [IncidentState.VERIFYING],
    IncidentState.VERIFYING: [IncidentState.AWAITING_APPROVAL],
    IncidentState.AWAITING_APPROVAL: [IncidentState.APPROVED, IncidentState.REJECTED],
    IncidentState.APPROVED: [IncidentState.DEPLOYED],
    IncidentState.DEPLOYED: [],
    IncidentState.REJECTED: [],
}


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TimelineEntry(BaseModel):
    state: IncidentState
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    diff: str | None = None
    result: str | None = None
    detail: str | None = None


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------

class Incident(BaseModel):
    incident_id: str
    decoy_id: str
    real_asset_id: str
    technique: str
    state: IncidentState
    timeline: list[TimelineEntry] = Field(default_factory=list)
    patch_diff: str | None = None
    approver: str | None = None


class IncidentSummary(BaseModel):
    incident_id: str
    decoy_id: str
    real_asset_id: str
    technique: str
    state: IncidentState
    created_at: str | None = None
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    incident_id: str
    action: str  # "approve" | "reject"
    approver: str
    reason: str | None = None
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ---------------------------------------------------------------------------
# Request / Response bodies
# ---------------------------------------------------------------------------

class ApproveRequest(BaseModel):
    approver: str


class RejectRequest(BaseModel):
    approver: str
    reason: str


class InternalDecoyEvent(BaseModel):
    """Raw decoy event from the correlation engine."""
    timestamp: str
    decoy_id: str
    source_ip: str
    session_id: str
    technique: str
    raw_payload: str | None = None


class InternalCrsStatus(BaseModel):
    """State transition from the Buttercup CRS adapter."""
    incident_id: str
    state: IncidentState
    diff: str | None = None
    result: str | None = None
    detail: str | None = None


class WebSocketMessage(BaseModel):
    """Message pushed to dashboard over WebSocket."""
    event: str  # "incident_created" | "incident_updated" | "audit_entry"
    data: dict[str, Any]
