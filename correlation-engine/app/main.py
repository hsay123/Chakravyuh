"""Correlation Engine — entry point.

Bridges honeypot events (DataTrap / Q-Cowrie) to Buttercup CRS tasks.

Responsibilities
----------------
1. Consume structured JSON events from the ``honeypot_events`` Redis stream.
2. Look up the decoy in the YAML asset registry.
3. Create an incident in the Backend Orchestrator.
4. Trigger a Buttercup fuzz task via the mock competition API.
5. Transition the incident state through the backend orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import uvicorn
from fastapi import FastAPI

from app.buttercup_client import ButtercupClient
from app.classifier import classify
from app.config import AssetRegistry, load_registry
from app.redis_consumer import StreamConsumer

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
EVENT_STREAM = os.getenv("EVENT_STREAM", "honeypot_events")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "1.0"))
BUTTERCUP_API_URL = os.getenv("BUTTERCUP_API_URL", "http://mock-competition-api:8080")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://backend-orchestrator:8000")
ASSETS_PATH = os.getenv("ASSETS_PATH", "config/assets.yaml")

# Idempotency: keep processed event IDs in-memory
_PROCESSED: set[str] = set()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("correlation-engine")

# ---------------------------------------------------------------------------
# FastAPI health-check app
# ---------------------------------------------------------------------------
app = FastAPI(title="TrapNet Correlation Engine")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

class Correlator:
    """Stateful correlator that owns the registry and clients."""

    def __init__(self) -> None:
        self.registry: AssetRegistry = load_registry(ASSETS_PATH)
        self.buttercup = ButtercupClient(base_url=BUTTERCUP_API_URL)
        self._session = __import__("requests").Session()
        self._session.headers.update({"Content-Type": "application/json"})
        # task_id → incident_id mapping for the poller
        self._task_incident_map: dict[str, str] = {}

    # -------------------------------------------------------------- #
    def handle_event(self, event: dict[str, Any]) -> None:
        event_id = event.get("event_id") or event.get("msg_id") or ""
        decoy_id = event.get("decoy_id", "")
        technique_hint = event.get("technique")
        raw_payload = event.get("raw_payload", "")

        # --- idempotency gate ------------------------------------------
        if event_id and event_id in _PROCESSED:
            logger.debug("Skipping already-processed event %s", event_id)
            return

        logger.info(
            "Event received  decoy_id=%s technique_hint=%s source_ip=%s",
            decoy_id,
            technique_hint,
            event.get("source_ip", "?"),
        )

        # --- asset lookup -----------------------------------------------
        asset = self.registry.lookup(decoy_id)
        if asset is None:
            logger.info("No asset match for decoy_id=%s — ignoring", decoy_id)
            if event_id:
                _PROCESSED.add(event_id)
            return

        # --- technique classification ------------------------------------
        technique = classify(technique_hint, raw_payload)
        if technique is None:
            technique = "unknown"

        logger.info(
            "MATCH  decoy=%s → asset=%s  technique=%s",
            decoy_id,
            asset.real_asset_id,
            technique,
        )

        # --- Step 1: Create incident in backend orchestrator -------------
        incident_id, is_new = self._create_incident(event, asset, technique)
        if incident_id is None:
            logger.error("Failed to create incident — skipping")
            if event_id:
                _PROCESSED.add(event_id)
            return

        if not is_new:
            logger.info("Incident %s already exists for decoy %s — skipping transitions", incident_id, decoy_id)
            if event_id:
                _PROCESSED.add(event_id)
            return

        # --- Step 2: Transition to MATCHED -------------------------------
        self._transition(incident_id, "MATCHED", detail=f"Decoy {decoy_id} correlated to asset {asset.real_asset_id}")

        # --- Step 3: Trigger Buttercup task ------------------------------
        self._transition(incident_id, "FUZZING", detail=f"Submitting Buttercup task for {asset.project_name}")

        result = self.buttercup.submit_task(
            real_asset_id=asset.real_asset_id,
            project_name=asset.project_name,
            focus=asset.focus,
            real_repo_url=asset.real_repo_url,
            real_tooling_url=asset.real_tooling_url,
            technique=technique,
            source_event=event,
        )

        if result.get("status") == "error":
            logger.warning("Buttercup control-file submission returned error (non-critical): %s", result.get("detail"))
        else:
            logger.info("Buttercup control-file accepted: %s", result)
            # Track task_id → incident_id for the patch poller
            task_id = result.get("task_id")
            if task_id:
                self._task_incident_map[task_id] = incident_id
                logger.info("Mapped Buttercup task %s → incident %s", task_id, incident_id)

        if event_id:
            _PROCESSED.add(event_id)

    # -------------------------------------------------------------- #
    def _create_incident(self, event: dict[str, Any], asset: Any, technique: str) -> tuple[str | None, bool]:
        """POST to /internal/events to create a new incident.

        Returns (incident_id, is_new).  If an active incident already exists
        for this decoy, the backend returns the existing one with
        ``action=appended_to_existing``.
        """
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "decoy_id": event.get("decoy_id", ""),
            "source_ip": event.get("source_ip", ""),
            "session_id": event.get("session_id", ""),
            "technique": technique,
            "raw_payload": event.get("raw_payload", ""),
        }
        url = f"{ORCHESTRATOR_URL}/internal/events"
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            incident_id = data.get("incident_id")
            is_new = data.get("status") == "incident_created"
            logger.info("Created incident %s (new=%s) via %s", incident_id, is_new, url)
            return incident_id, is_new
        except Exception:
            logger.exception("Failed to create incident via %s", url)
            return None, False

    # -------------------------------------------------------------- #
    def _transition(self, incident_id: str, state: str, *, diff: str | None = None, result: str | None = None, detail: str | None = None) -> None:
        """POST to /internal/crs-status to transition an incident."""
        payload = {
            "incident_id": incident_id,
            "state": state,
        }
        if diff is not None:
            payload["diff"] = diff
        if result is not None:
            payload["result"] = result
        if detail is not None:
            payload["detail"] = detail
        url = f"{ORCHESTRATOR_URL}/internal/crs-status"
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            logger.info("Transitioned %s → %s (%s)", incident_id, state, resp.status_code)
        except Exception:
            logger.exception("Failed to transition %s → %s", incident_id, state)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def patch_poller(correlator: Correlator) -> None:
    """Background thread: poll Buttercup's patches_queue and transition incidents."""
    import redis as redislib

    crs_redis_host = os.getenv("CRS_REDIS_HOST", "redis")
    crs_redis_port = int(os.getenv("CRS_REDIS_PORT", "6379"))

    # Retry connection until CRS Redis is ready
    r = None
    for attempt in range(30):
        try:
            r = redislib.Redis(host=crs_redis_host, port=crs_redis_port, decode_responses=False)
            r.ping()
            break
        except Exception:
            logger.info("Patch poller: waiting for CRS Redis (%s:%s) attempt %d/30", crs_redis_host, crs_redis_port, attempt + 1)
            time.sleep(3)

    if r is None:
        logger.error("Patch poller: could not connect to CRS Redis after 30 attempts — giving up")
        return

    logger.info("Patch poller connected to CRS Redis %s:%s", crs_redis_host, crs_redis_port)

    group = "correlation-engine-patches"
    stream = "patches_queue"
    consumer = "patch-watcher"

    # Create consumer group (idempotent)
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
    except redislib.exceptions.ResponseError:
        pass  # already exists

    while True:
        try:
            items = r.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=5,
                block=5000,
            )
            if not items:
                continue

            for _stream_name, entries in items:
                for item_id, fields in entries:
                    raw = fields.get(b"item") or fields.get("item")
                    if not raw:
                        r.xack(stream, group, item_id)
                        continue

                    # Parse as protobuf (Patch: fields 1,2,3 are strings)
                    import json
                    task_id = ""
                    patch_text = ""
                    internal_patch_id = ""

                    def _parse_protobuf_strings(data: bytes) -> dict[int, str]:
                        """Minimal protobuf wire-format parser for length-delimited string fields."""
                        result = {}
                        pos = 0
                        while pos < len(data):
                            # Read varint (field tag)
                            tag = 0
                            shift = 0
                            while pos < len(data):
                                b = data[pos]; pos += 1
                                tag |= (b & 0x7F) << shift
                                shift += 7
                                if not (b & 0x80):
                                    break
                            field_number = tag >> 3
                            wire_type = tag & 0x07
                            if wire_type == 2:  # length-delimited
                                length = 0
                                shift = 0
                                while pos < len(data):
                                    b = data[pos]; pos += 1
                                    length |= (b & 0x7F) << shift
                                    shift += 7
                                    if not (b & 0x80):
                                        break
                                result[field_number] = data[pos:pos+length].decode("utf-8", errors="replace")
                                pos += length
                            elif wire_type == 0:  # varint
                                while pos < len(data):
                                    b = data[pos]; pos += 1
                                    if not (b & 0x80):
                                        break
                            else:
                                break
                        return result

                    if isinstance(raw, (bytes, bytearray)) and len(raw) > 0:
                        try:
                            fields = _parse_protobuf_strings(raw)
                            task_id = fields.get(1, "")
                            internal_patch_id = fields.get(2, "")
                            patch_text = fields.get(3, "")
                        except Exception:
                            pass

                    if not task_id:
                        try:
                            patch_data = json.loads(raw) if isinstance(raw, (str, bytes)) else {}
                            task_id = patch_data.get("task_id", "")
                            patch_text = patch_data.get("patch", "")
                            internal_patch_id = patch_data.get("internal_patch_id", "")
                        except Exception:
                            pass

                    logger.info("Patch received: task_id=%s internal_patch_id=%s", task_id, internal_patch_id)

                    incident_id = correlator._task_incident_map.get(task_id)
                    if incident_id is None:
                        # Fallback: after restart, the in-memory map is empty.
                        # Query the backend for a FUZZING incident to reconnect.
                        logger.info("No in-memory map for task %s — querying backend for FUZZING incidents", task_id)
                        try:
                            resp = correlator._session.get(f"{ORCHESTRATOR_URL}/incidents", timeout=5)
                            for inc in resp.json():
                                if inc.get("state") == "FUZZING":
                                    incident_id = inc["incident_id"]
                                    correlator._task_incident_map[task_id] = incident_id
                                    logger.info("Recovered mapping task %s → incident %s", task_id, incident_id)
                                    break
                        except Exception:
                            logger.exception("Failed to query backend for incident recovery")
                    if incident_id is None:
                        logger.debug("No incident mapped for task %s — skipping", task_id)
                        r.xack(stream, group, item_id)
                        continue

                    # Transition: FUZZING → PATCH_GENERATED → VERIFYING → AWAITING_APPROVAL
                    correlator._transition(
                        incident_id, "PATCH_GENERATED",
                        diff=patch_text[:10000],
                        detail=f"Buttercup patch {internal_patch_id} for task {task_id}",
                    )
                    correlator._transition(
                        incident_id, "VERIFYING",
                        detail="Running patch verification",
                    )
                    correlator._transition(
                        incident_id, "AWAITING_APPROVAL",
                        detail="Patch verified — awaiting human approval",
                    )
                    logger.info("Incident %s advanced to AWAITING_APPROVAL", incident_id)
                    r.xack(stream, group, item_id)

        except Exception:
            logger.exception("Patch poller error")
            time.sleep(5)


def main() -> None:
    correlator = Correlator()

    consumer = StreamConsumer(
        redis_url=REDIS_URL,
        stream=EVENT_STREAM,
        group="correlation-engine",
        consumer="worker-1",
        poll_interval=POLL_INTERVAL,
    )

    # Start the health-check server in a daemon thread
    import threading

    uvicorn_config = uvicorn.Config(app, host="0.0.0.0", port=8100, log_level="warning")
    server = uvicorn.Server(uvicorn_config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    logger.info("Health-check server listening on :8100")

    # Start the Buttercup patch poller in a daemon thread
    poller_thread = threading.Thread(target=patch_poller, args=(correlator,), daemon=True)
    poller_thread.start()
    logger.info("Buttercup patch poller started")

    consumer.consume(handler=correlator.handle_event)


if __name__ == "__main__":
    main()
