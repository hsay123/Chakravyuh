"""Thin client for triggering Buttercup fuzz/patch tasks via the mock competition API."""

from __future__ import annotations

import io
import json
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class ButtercupClient:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ------------------------------------------------------------------
    def submit_task(
        self,
        *,
        real_asset_id: str,
        project_name: str,
        focus: str,
        real_repo_url: str,
        real_tooling_url: str,
        technique: str,
        source_event: dict[str, Any],
    ) -> dict[str, Any]:
        """Upload a control-file to the mock competition API to queue a Buttercup run.

        The /control-file/ endpoint expects a multipart file upload containing
        a JSON array of task objects.
        """
        task = {
            "asset_id": real_asset_id,
            "project_name": project_name,
            "focus": focus,
            "repo_url": real_repo_url,
            "tooling_url": real_tooling_url,
            "trigger_technique": technique,
            "source_event": source_event,
            "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        control_data = [task]
        file_content = json.dumps(control_data).encode("utf-8")

        url = f"{self.base_url}/control-file/"
        logger.info("Submitting control-file → %s  asset=%s technique=%s", url, real_asset_id, technique)

        try:
            files = {"file": ("control.json", io.BytesIO(file_content), "application/json")}
            resp = self.session.post(url, files=files, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            logger.info("Control-file accepted: %s", result)
            return result
        except requests.RequestException as exc:
            logger.error("Control-file submission failed: %s", exc)
            return {"status": "error", "detail": str(exc)}
