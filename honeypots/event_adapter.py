#!/usr/bin/env python3
"""DataTrap honeypot event adapter.

Tails DataTrap JSON log files, classifies attack techniques via pattern
matching, and publishes standardized events to Redis stream
`honeypot_events` using XADD for downstream consumption by the
Correlation Engine.

DataTrap emits JSON lines like:
  {"dd-honeypot": true, "time": "...", "session-id": "...",
   "type": "http", "name": "TrapNet-HTTP-Decoy",
   "login": {"client_ip": "..."}}
"""

from __future__ import annotations

import json
import os
import re
import signal
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import redis

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_STREAM: str = os.getenv("REDIS_STREAM", "honeypot_events")
LOG_DIR: Path = Path(os.getenv("HONEYPOT_LOG_DIR", "/var/log/honeypot"))
POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "0.5"))
MAX_STREAM_LEN: int = int(os.getenv("MAX_STREAM_LEN", "50000"))

# ---------------------------------------------------------------------------
# Technique classification
# ---------------------------------------------------------------------------

_SHELL_META_RE = re.compile(r"[;|&`$(){}]")
_SQL_KEYWORDS_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|FROM|WHERE|INTO|TABLE)\b",
    re.IGNORECASE,
)


def classify_technique(payload: str) -> str:
    """Return the attack technique label for a raw payload string."""
    if len(payload) > 100:
        return "buffer_overflow_probe"
    if _SHELL_META_RE.search(payload):
        return "command_injection"
    if _SQL_KEYWORDS_RE.search(payload):
        return "sql_injection"
    return "unknown"


def classify_from_event(event: dict[str, Any]) -> str:
    """Infer technique from a structured DataTrap event dict.

    DataTrap connection-level events do not carry request details,
    so we classify based on the honeypot type and any available info.
    """
    # If the event has request-level fields (command, body, path, query),
    # classify from those.
    command = event.get("command", "")
    body = event.get("body", "")
    path = event.get("path", "")
    query = event.get("query_string", "") or event.get("query", "")
    filename = event.get("filename", "")

    text = command or body or path or query or filename

    if text:
        return classify_technique(text)

    # For connection-level events, classify based on honeypot type.
    hp_type = event.get("type", "")
    if hp_type == "ssh":
        return "credential_bruteforce"  # SSH connection = brute-force attempt
    if hp_type == "http":
        return "unknown"  # HTTP connection alone is ambiguous

    return "unknown"


# ---------------------------------------------------------------------------
# Event normalizer (DataTrap format)
# ---------------------------------------------------------------------------


def normalize_event(raw: dict[str, Any]) -> dict[str, str]:
    """Convert a DataTrap log entry into the standard event schema.

    DataTrap emits:
      {"dd-honeypot": true, "time": "...", "session-id": "...",
       "type": "http", "name": "...", "login": {"client_ip": "..."}}

    Also handles richer events that may include command, body, path, etc.
    """
    # DataTrap uses "time", not "timestamp"
    timestamp = raw.get("time", raw.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))

    # DataTrap nests client_ip in login dict
    login_info = raw.get("login", {})
    source_ip = login_info.get("client_ip", raw.get("src_ip", "0.0.0.0"))

    # DataTrap uses "session-id" (with hyphen)
    session_id = raw.get("session-id", raw.get("session_id", str(uuid.uuid4())[:12]))

    decoy_id = _resolve_decoy_id(raw)
    technique = classify_from_event(raw)
    raw_payload = _extract_raw_payload(raw)

    return {
        "timestamp": timestamp,
        "decoy_id": decoy_id,
        "source_ip": source_ip,
        "session_id": session_id,
        "technique": technique,
        "raw_payload": raw_payload,
    }


def _resolve_decoy_id(event: dict[str, Any]) -> str:
    """Map the event back to a honeypot decoy identifier.

    DataTrap uses "type" field (ssh, http, etc.) and "name" field.
    """
    hp_type = event.get("type", "")
    name = event.get("name", "")

    # Match by name first (more specific)
    if "ssh" in name.lower():
        return "fake-ssh-honeypot"
    if "http" in name.lower():
        return "fake-http-honeypot"

    # Fall back to type
    if hp_type == "ssh":
        return "fake-ssh-honeypot"
    if hp_type == "http":
        return "fake-http-honeypot"

    return "unknown-decoy"


def _extract_raw_payload(event: dict[str, Any]) -> str:
    """Return the most relevant payload string from the event."""
    return (
        event.get("command")
        or event.get("body")
        or event.get("path")
        or event.get("query", "")
        or event.get("password", "")
        or ""
    )


# ---------------------------------------------------------------------------
# Redis publisher
# ---------------------------------------------------------------------------


class StreamPublisher:
    """Publishes normalized events to a Redis stream with consumer groups."""

    def __init__(self, client: redis.Redis, stream: str, max_len: int) -> None:
        self._client = client
        self._stream = stream
        self._max_len = max_len
        self._ensure_group()

    def _ensure_group(self) -> None:
        """Create the consumer group if it does not already exist."""
        try:
            self._client.xgroup_create(
                self._stream, "honeypot_consumers", id="0", mkstream=True
            )
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, event: dict[str, str]) -> str:
        """XADD the event and return the message ID."""
        msg_id: str = self._client.xadd(
            self._stream, event, maxlen=self._max_len
        )
        return msg_id


# ---------------------------------------------------------------------------
# Log tailer
# ---------------------------------------------------------------------------


def tail_log(path: Path, callback: Any) -> None:
    """Follow *path* and invoke *callback* for each new JSON line.

    If the file does not exist yet, block until it appears.
    """
    while not path.exists():
        time.sleep(POLL_INTERVAL)

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        fh.seek(0, 2)
        while True:
            line = fh.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            callback(entry)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_running = True


def _handle_signal(signum: int, _frame: Any) -> None:
    global _running
    _running = False
    print(f"[event_adapter] Caught signal {signum}, shutting down.")


def main() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
    )
    publisher = StreamPublisher(client, REDIS_STREAM, MAX_STREAM_LEN)

    def _process_event(raw: dict[str, Any]) -> None:
        """Normalize a single event and publish to Redis."""
        event = normalize_event(raw)
        try:
            msg_id = publisher.publish(event)
            print(
                f"[event_adapter] {event['technique']} "
                f"from {event['source_ip']} -> {msg_id}"
            )
        except redis.ConnectionError as exc:
            print(
                f"[event_adapter] Redis connection error: {exc}",
                file=sys.stderr,
            )

    print(f"[event_adapter] Watching {LOG_DIR} for honeypot logs ...")
    print(f"[event_adapter] Publishing to Redis stream '{REDIS_STREAM}'")

    log_files = list(LOG_DIR.glob("*.json"))
    if not log_files:
        print(
            f"[event_adapter] No .json log files in {LOG_DIR}; "
            "waiting for DataTrap to create them."
        )

    # Track which files we are already tailing so we do not double-tail.
    tailed: set[Path] = set()

    while _running:
        # Discover new log files dynamically.
        for log_file in LOG_DIR.glob("*.json"):
            if log_file not in tailed:
                tailed.add(log_file)
                print(f"[event_adapter] Tailing {log_file}")

        # Process any already-discovered files (simplified single-threaded
        # tail for prototype clarity; production would use threads or
        # asyncio tasks per file).
        for log_file in list(tailed):
            tail_log(log_file, _process_event)

        if not tailed:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
