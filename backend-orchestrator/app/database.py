"""SQLite database layer for the Backend Orchestrator."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import (
    AuditEntry,
    Incident,
    IncidentState,
    IncidentSummary,
    TimelineEntry,
    VALID_TRANSITIONS,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "trapnet.db"
AUDIT_PATH = Path(__file__).resolve().parent.parent / "audit.jsonl"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id   TEXT PRIMARY KEY,
    decoy_id      TEXT NOT NULL,
    real_asset_id TEXT NOT NULL,
    technique     TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT 'DETECTED',
    patch_diff    TEXT,
    approver      TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS timeline (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id  TEXT NOT NULL REFERENCES incidents(incident_id),
    state        TEXT NOT NULL,
    ts           TEXT NOT NULL,
    diff         TEXT,
    result       TEXT,
    detail       TEXT
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _get_conn()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialised at %s", DB_PATH)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Incident CRUD
# ---------------------------------------------------------------------------

def _row_to_incident(row: sqlite3.Row, timeline_rows: list[sqlite3.Row]) -> Incident:
    return Incident(
        incident_id=row["incident_id"],
        decoy_id=row["decoy_id"],
        real_asset_id=row["real_asset_id"],
        technique=row["technique"],
        state=IncidentState(row["state"]),
        timeline=[
            TimelineEntry(
                state=IncidentState(t["state"]),
                ts=t["ts"],
                diff=t["diff"],
                result=t["result"],
                detail=t["detail"],
            )
            for t in timeline_rows
        ],
        patch_diff=row["patch_diff"],
        approver=row["approver"],
    )


def get_incident(incident_id: str) -> Incident | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        if row is None:
            return None
        t_rows = conn.execute(
            "SELECT * FROM timeline WHERE incident_id = ? ORDER BY id",
            (incident_id,),
        ).fetchall()
        return _row_to_incident(row, t_rows)
    finally:
        conn.close()


def list_incidents() -> list[IncidentSummary]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT incident_id, decoy_id, real_asset_id, technique, state, created_at, updated_at "
            "FROM incidents ORDER BY created_at DESC"
        ).fetchall()
        return [
            IncidentSummary(
                incident_id=r["incident_id"],
                decoy_id=r["decoy_id"],
                real_asset_id=r["real_asset_id"],
                technique=r["technique"],
                state=IncidentState(r["state"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def create_incident(
    decoy_id: str,
    real_asset_id: str,
    technique: str,
    *,
    state: IncidentState = IncidentState.DETECTED,
    extra_fields: dict[str, Any] | None = None,
) -> Incident:
    now = datetime.utcnow().isoformat() + "Z"
    incident_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO incidents (incident_id, decoy_id, real_asset_id, technique, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (incident_id, decoy_id, real_asset_id, technique, state.value, now, now),
        )
        conn.execute(
            "INSERT INTO timeline (incident_id, state, ts) VALUES (?, ?, ?)",
            (incident_id, state.value, now),
        )
        conn.commit()
        logger.info("Created incident %s in state %s", incident_id, state.value)
    finally:
        conn.close()

    incident = get_incident(incident_id)
    assert incident is not None
    return incident


def transition_incident(
    incident_id: str,
    new_state: IncidentState,
    *,
    diff: str | None = None,
    result: str | None = None,
    detail: str | None = None,
) -> Incident:
    """Transition an incident to a new state. Raises ValueError on invalid transition."""
    incident = get_incident(incident_id)
    if incident is None:
        raise KeyError(f"Incident {incident_id} not found")

    allowed = VALID_TRANSITIONS.get(incident.state, [])
    if new_state not in allowed:
        raise ValueError(
            f"Invalid transition: {incident.state.value} → {new_state.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )

    now = datetime.utcnow().isoformat() + "Z"
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE incidents SET state = ?, updated_at = ?, patch_diff = COALESCE(?, patch_diff), "
            "approver = COALESCE(?, approver) WHERE incident_id = ?",
            (new_state.value, now, diff, None, incident_id),
        )
        conn.execute(
            "INSERT INTO timeline (incident_id, state, ts, diff, result, detail) VALUES (?, ?, ?, ?, ?, ?)",
            (incident_id, new_state.value, now, diff, result, detail),
        )
        conn.commit()
        logger.info("Transitioned incident %s: %s → %s", incident_id, incident.state.value, new_state.value)
    finally:
        conn.close()

    return get_incident(incident_id)  # type: ignore[return-value]


def approve_incident(incident_id: str, approver: str) -> Incident:
    """Approve an incident — marks it as APPROVED with the approver recorded."""
    incident = get_incident(incident_id)
    if incident is None:
        raise KeyError(f"Incident {incident_id} not found")
    if incident.state != IncidentState.AWAITING_APPROVAL:
        raise ValueError(
            f"Incident is in state {incident.state.value}, must be AWAITING_APPROVAL to approve"
        )

    now = datetime.utcnow().isoformat() + "Z"
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE incidents SET state = ?, approver = ?, updated_at = ? WHERE incident_id = ?",
            (IncidentState.APPROVED.value, approver, now, incident_id),
        )
        conn.execute(
            "INSERT INTO timeline (incident_id, state, ts, detail) VALUES (?, ?, ?, ?)",
            (incident_id, IncidentState.APPROVED.value, now, f"Approved by {approver}"),
        )
        conn.commit()
        logger.info("Approved incident %s by %s", incident_id, approver)
    finally:
        conn.close()

    return get_incident(incident_id)  # type: ignore[return-value]


def reject_incident(incident_id: str, approver: str, reason: str) -> Incident:
    """Reject an incident."""
    incident = get_incident(incident_id)
    if incident is None:
        raise KeyError(f"Incident {incident_id} not found")
    if incident.state != IncidentState.AWAITING_APPROVAL:
        raise ValueError(
            f"Incident is in state {incident.state.value}, must be AWAITING_APPROVAL to reject"
        )

    now = datetime.utcnow().isoformat() + "Z"
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE incidents SET state = ?, approver = ?, updated_at = ? WHERE incident_id = ?",
            (IncidentState.REJECTED.value, approver, now, incident_id),
        )
        conn.execute(
            "INSERT INTO timeline (incident_id, state, ts, detail) VALUES (?, ?, ?, ?)",
            (incident_id, IncidentState.REJECTED.value, now, f"Rejected by {approver}: {reason}"),
        )
        conn.commit()
        logger.info("Rejected incident %s by %s: %s", incident_id, approver, reason)
    finally:
        conn.close()

    return get_incident(incident_id)  # type: ignore[return-value]


def find_incident_by_decoy(decoy_id: str, *, active_only: bool = True) -> Incident | None:
    """Find an incident by decoy_id. Optionally filter to non-terminal states."""
    conn = _get_conn()
    try:
        terminal_states = {IncidentState.DEPLOYED.value, IncidentState.REJECTED.value}
        if active_only:
            placeholders = ",".join("?" for _ in terminal_states)
            row = conn.execute(
                f"SELECT * FROM incidents WHERE decoy_id = ? AND state NOT IN ({placeholders}) "
                "ORDER BY created_at DESC LIMIT 1",
                (decoy_id, *terminal_states),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM incidents WHERE decoy_id = ? ORDER BY created_at DESC LIMIT 1",
                (decoy_id,),
            ).fetchone()
        if row is None:
            return None
        t_rows = conn.execute(
            "SELECT * FROM timeline WHERE incident_id = ? ORDER BY id",
            (row["incident_id"],),
        ).fetchall()
        return _row_to_incident(row, t_rows)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Audit log (append-only JSONL)
# ---------------------------------------------------------------------------

def append_audit(entry: AuditEntry) -> None:
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
    logger.info("Audit entry written: %s on %s by %s", entry.action, entry.incident_id, entry.approver)


def read_audit_log() -> list[AuditEntry]:
    if not AUDIT_PATH.exists():
        return []
    entries: list[AuditEntry] = []
    with open(AUDIT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(AuditEntry.model_validate_json(line))
    return entries
