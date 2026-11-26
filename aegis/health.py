"""Opt-in recorder counters stored locally with no clip or account data."""
from __future__ import annotations

import json
import threading
import time

from . import paths
from .log import log

COUNTERS = (
    "capture_attempts", "capture_ready", "capture_start_ms",
    "save_attempts", "saves", "save_ms", "frames_output", "frames_dropped",
)


class HealthMetrics:
    def __init__(self, cfg):
        self.cfg = cfg
        self._lock = threading.Lock()
        self._file = paths.data_root() / "health-metrics.json"
        self._counts = dict.fromkeys(COUNTERS, 0)
        self._last_write = time.monotonic()
        self._dirty = False
        if self._file.is_file():
            try:
                values = json.loads(self._file.read_text(encoding="utf-8"))
                for key in COUNTERS:
                    value = values.get(key, 0)
                    if type(value) is int and value >= 0:
                        self._counts[key] = value
            except (OSError, ValueError, AttributeError):
                log("Could not read the saved app health counts.")

    @property
    def enabled(self) -> bool:
        return self.cfg.get("metrics.enabled") is True

    def add(self, **deltas: int) -> None:
        if not self.enabled:
            return
        with self._lock:
            if not self.enabled:
                return
            for key in COUNTERS:
                self._counts[key] += max(0, deltas.get(key, 0))
            self._dirty = self._dirty or any(deltas.values())
            if self._dirty and time.monotonic() - self._last_write >= 30:
                self._write()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return self._counts.copy() if self.enabled else {}

    def flush(self) -> None:
        with self._lock:
            if self._dirty:
                self._write()

    def _write(self) -> None:
        self._last_write = time.monotonic()
        try:
            paths.atomic_write_text(self._file, json.dumps(self._counts))
            self._dirty = False
        except OSError as exc:
            log(f"Could not save the app health counts: {exc}")
