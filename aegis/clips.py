"""Clip catalog — the source of truth for the dashboard and montage builder.

Each saved clip becomes one record persisted to ``clips.json``. We store the
file path (clips stay where OBS wrote them) plus metadata the engine knows at
capture time (kills, map, round, side) and user edits (title, tags, favorite),
and per-target upload status. JSON keeps it dependency-free and easy to inspect;
a single lock guards concurrent access from the engine thread and web requests.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import paths
from .log import log


@dataclass
class Clip:
    id: str
    path: str
    created: float          # epoch seconds (caller stamps it)
    kills: int = 1
    map_name: str = "unknown"
    round_n: int = 0
    side: str = "?"
    title: str = ""
    tags: list[str] = field(default_factory=list)
    favorite: bool = False
    size_mb: float = 0.0
    duration: float = 0.0
    thumb: str = ""                       # thumbnail filename under thumbs_dir
    uploads: dict[str, str] = field(default_factory=dict)  # target -> "ok"|"error: .."

    def exists(self) -> bool:
        return Path(self.path).exists()


class Catalog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clips: dict[str, Clip] = {}
        self._load()

    def _load(self) -> None:
        f = paths.catalog_file()
        if not f.exists():
            return
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            for rec in raw:
                self._clips[rec["id"]] = Clip(**rec)
        except Exception as e:
            log(f"clips.json unreadable ({e}); starting empty")

    def _save_locked(self) -> None:
        data = [asdict(c) for c in self._clips.values()]
        paths.atomic_write_text(paths.catalog_file(), json.dumps(data, indent=2))

    def add(self, clip: Clip) -> None:
        with self._lock:
            self._clips[clip.id] = clip
            self._save_locked()

    def get(self, clip_id: str) -> Clip | None:
        with self._lock:
            return self._clips.get(clip_id)

    def update(self, clip_id: str, **fields: Any) -> Clip | None:
        with self._lock:
            c = self._clips.get(clip_id)
            if c is None:
                return None
            for k, v in fields.items():
                if hasattr(c, k):
                    setattr(c, k, v)
            self._save_locked()
            return c

    def set_upload_status(self, clip_id: str, target: str, status: str) -> None:
        with self._lock:
            c = self._clips.get(clip_id)
            if c is not None:
                c.uploads[target] = status
                self._save_locked()

    def remove(self, clip_id: str, delete_file: bool = False) -> bool:
        with self._lock:
            c = self._clips.pop(clip_id, None)
            if c is None:
                return False
            self._save_locked()
        if delete_file:
            for p in (Path(c.path), paths.thumbs_dir() / c.thumb if c.thumb else None):
                try:
                    if p and p.exists():
                        p.unlink()
                except Exception as e:
                    log(f"Could not delete {p}: {e}")
        return True

    def list(self) -> list[Clip]:
        """Newest first."""
        with self._lock:
            return sorted(self._clips.values(), key=lambda c: c.created, reverse=True)
