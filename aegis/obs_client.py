"""OBS WebSocket wrapper — lazy, reconnecting, never fatal.

The engine must keep running even if OBS is closed or the Replay Buffer is off,
so every method here degrades to a logged no-op / False instead of raising. The
connection is created on first use and dropped on error so the next call retries.
"""
from __future__ import annotations

import logging
import threading

from obsws_python import ReqClient

from .log import log

# obsws-python logs a full traceback every time OBS is unreachable. We handle
# that case ourselves with a one-line message, so silence its logger.
logging.getLogger("obsws_python").setLevel(logging.CRITICAL)


class ObsClient:
    def __init__(self, host: str, port: int, password: str):
        self._host = host
        self._port = port
        self._password = password or None
        self._client: ReqClient | None = None
        self._lock = threading.Lock()
        self._warned = False  # so we log "unreachable" once, not every poll

    def _connect(self) -> ReqClient | None:
        if self._client is not None:
            return self._client
        try:
            self._client = ReqClient(
                host=self._host, port=self._port,
                password=self._password, timeout=3,
            )
            log(f"OBS WebSocket connected at {self._host}:{self._port}")
            self._warned = False
        except Exception as e:
            # The dashboard polls status every few seconds; only log the first
            # failure of a streak so a closed OBS doesn't flood the log.
            if not self._warned:
                log(f"OBS WebSocket unreachable: {e}")
                self._warned = True
            self._client = None
        return self._client

    def _drop(self) -> None:
        self._client = None

    def connected(self) -> bool:
        with self._lock:
            return self._connect() is not None

    def save_replay_buffer(self) -> bool:
        """Tell OBS to flush its replay buffer to disk. True on success."""
        with self._lock:
            c = self._connect()
            if c is None:
                return False
            try:
                c.save_replay_buffer()
                return True
            except Exception as e:
                log(f"OBS save_replay_buffer failed: {e}")
                self._drop()
                return False

    def replay_buffer_active(self) -> bool:
        """Whether the Replay Buffer is currently running (best effort)."""
        with self._lock:
            c = self._connect()
            if c is None:
                return False
            try:
                return bool(c.get_replay_buffer_status().output_active)
            except Exception:
                return False
