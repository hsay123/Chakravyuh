"""Reliable Redis stream consumer with consumer-group support."""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any, Callable

import redis

logger = logging.getLogger(__name__)

# Reconnection back-off constants
INITIAL_BACKOFF = 0.5
MAX_BACKOFF = 10.0


class StreamConsumer:
    """Reads from a Redis stream using a consumer group.

    Parameters
    ----------
    redis_url : str
        Redis connection string (e.g. ``redis://redis:6379/0``).
    stream : str
        Stream key to consume.
    group : str
        Consumer group name.
    consumer : str
        Individual consumer name within the group.
    poll_interval : float
        Seconds to block on ``XREADGROUP`` when no messages are available.
    """

    def __init__(
        self,
        redis_url: str,
        stream: str,
        group: str = "correlation-engine",
        consumer: str = "worker-1",
        poll_interval: float = 1.0,
    ) -> None:
        self.redis_url = redis_url
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self.poll_interval = poll_interval
        self._client: redis.Redis | None = None  # lazy init
        self._running = True

        # Graceful-shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------
    def _handle_signal(self, signum: int, _frame: Any) -> None:
        logger.info("Received signal %s — shutting down gracefully", signum)
        self._running = False

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    # ------------------------------------------------------------------
    def _ensure_group(self) -> None:
        """Create the consumer group if it does not exist."""
        try:
            self.client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
            logger.info("Created consumer group '%s' on stream '%s'", self.group, self.stream)
        except redis.exceptions.ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                pass  # already exists
            else:
                raise

    # ------------------------------------------------------------------
    def consume(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Blocking loop — ``handler(event_dict)`` is invoked per message.

        Messages are acknowledged only *after* the handler returns without
        raising, providing at-least-once semantics.
        """
        self._ensure_group()
        backoff = INITIAL_BACKOFF

        logger.info("Starting consumer loop on stream='%s' group='%s'", self.stream, self.group)

        while self._running:
            try:
                entries = self.client.xreadgroup(
                    self.group,
                    self.consumer,
                    {self.stream: ">"},
                    count=10,
                    block=int(self.poll_interval * 1000),
                )
                backoff = INITIAL_BACKOFF  # reset on success
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                logger.warning("Redis read failed (%s) — retrying in %.1fs", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            if not entries:
                continue

            for _stream_name, messages in entries:
                for msg_id, fields in messages:
                    try:
                        event = _deserialize(fields)
                        event["msg_id"] = msg_id
                        handler(event)
                        self.client.xack(self.stream, self.group, msg_id)
                        logger.debug("Acknowledged message %s", msg_id)
                    except Exception:
                        logger.exception("Unhandled error processing message %s — not acking", msg_id)

        logger.info("Consumer loop stopped")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #

def _deserialize(fields: dict[str, str]) -> dict[str, Any]:
    """Redis streams store all values as strings; attempt JSON decode."""
    result: dict[str, Any] = {}
    for key, value in fields.items():
        try:
            result[key] = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            result[key] = value
    return result
