"""Thin client for triggering Buttercup fuzz/patch tasks via the mock competition API."""

from __future__ import annotations

import io
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

# SHA256 hashes of the uploaded tarballs (repo + tooling)
REPO_SHA256 = "41f69b29edf125be9ddf30517cf29d15956c6682869810d2b4c9dee35aeaec42"
TOOLING_SHA256 = "e26629cbec6c52367002e9a23c1d871526914dc00d2bf810941589dd10566d4b"


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

        The control-file format is a JSON array of task objects, each with:
          id, type, deadline, source (sha256 as url), round_id, created_at,
          updated_at, focus, project_name, commit, harnesses_included.
        """
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=2)
        task_id = str(uuid.uuid4())

        task = {
            "id": task_id,
            "type": "delta",
            "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "source": [
                {
                    "url": REPO_SHA256,
                    "type": "repo",
                    "sha256": REPO_SHA256,
                },
                {
                    "url": TOOLING_SHA256,
                    "type": "fuzz-tooling",
                    "sha256": TOOLING_SHA256,
                },
            ],
            "round_id": "trapnet-correlation",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "updated_at": now.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "focus": focus,
            "project_name": project_name,
            "commit": "v1.6.58",
            "harnesses_included": True,
        }

        file_content = json.dumps([task]).encode("utf-8")
        url = f"{self.base_url}/control-file/"
        logger.info("Submitting control-file → %s  asset=%s technique=%s task_id=%s", url, real_asset_id, technique, task_id)

        try:
            files = {"file": ("control.json", io.BytesIO(file_content), "application/json")}
            resp = self.session.post(url, files=files, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            logger.info("Control-file accepted: %s  task_id=%s", result, task_id)
            return {"status": "ok", "task_id": task_id, **result}
        except requests.RequestException as exc:
            logger.error("Control-file submission failed: %s", exc)
            return {"status": "error", "detail": str(exc)}
