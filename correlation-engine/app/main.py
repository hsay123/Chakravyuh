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
        incident_id = self._create_incident(event, asset, technique)
        if incident_id is None:
            logger.error("Failed to create incident — skipping")
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

        if event_id:
            _PROCESSED.add(event_id)

    # -------------------------------------------------------------- #
    def _create_incident(self, event: dict[str, Any], asset: Any, technique: str) -> str | None:
        """POST to /internal/events to create a new incident."""
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
            logger.info("Created incident %s via %s", incident_id, url)
            return incident_id
        except Exception:
            logger.exception("Failed to create incident via %s", url)
            return None

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

    consumer.consume(handler=correlator.handle_event)


if __name__ == "__main__":
    main()
