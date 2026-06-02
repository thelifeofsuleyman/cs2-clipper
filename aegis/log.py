"""Tiny timestamped logger.

Prints to stdout (so the console/tray log stays useful) and keeps the last N
lines in a ring buffer that the dashboard exposes at /api/logs — that's how the
web UI shows live activity without a logging framework.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

_BUFFER: deque[str] = deque(maxlen=500)
_lock = threading.Lock()


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with _lock:
        _BUFFER.append(line)
    print(line, flush=True)


def recent(limit: int = 200) -> list[str]:
    with _lock:
        items = list(_BUFFER)
    return items[-limit:]
