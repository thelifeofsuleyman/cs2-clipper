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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from . import paths
from .log import log


class ClipBudgetFull(OSError):
    def __init__(self):
        super().__init__("The clip storage budget is full. Free space in Recently deleted or increase the budget.")


class HighlightNotKept(ValueError):
    """The saved streak is below the configured per-match cutoff."""


def collection_names(values) -> list[str]:
    if (not isinstance(values, list) or len(values) > 30
            or any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 60
                   or any(ord(char) < 32 for char in value) for value in values)):
        raise ValueError("Choose up to 30 collection names of 1 to 60 characters.")
    return list(dict.fromkeys(value.strip() for value in values))


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
    match_id: str = ""
    match_mode: str = ""
    match_started: float = 0.0
    kill_markers: list[dict] = field(default_factory=list)
    deleted: bool = False
    collections: list[str] = field(default_factory=list)
    ranked_highlight: bool = False

    def exists(self) -> bool:
        return Path(self.path).is_file()


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

    def add(self, clip: Clip, budget: int = 0) -> None:
        with self._lock:
            if budget and self._used_bytes_locked(exclude=clip.id) + Path(clip.path).stat().st_size > budget:
                raise ClipBudgetFull()
            previous = self._clips.get(clip.id)
            self._clips[clip.id] = clip
            try:
                self._save_locked()
            except OSError:
                if previous is None:
                    del self._clips[clip.id]
                else:
                    self._clips[clip.id] = previous
                raise

    def get(self, clip_id: str, *, include_deleted: bool = False) -> Clip | None:
        with self._lock:
            clip = self._clips.get(clip_id)
            return clip if clip and (include_deleted or not clip.deleted) else None

    def restore(self, records: list[Clip], budget: int = 0) -> None:
        """Apply a backup in a single catalog write, keeping local paths that still work."""
        with self._lock:
            previous = self._clips
            current_bytes = self._used_bytes_locked() if budget else 0
            updated = previous.copy()
            for record in records:
                local = previous.get(record.id)
                if local:
                    still_exists = local.exists()
                    record = replace(record, path=local.path if still_exists else record.path,
                                     thumb=local.thumb, uploads=local.uploads, deleted=local.deleted,
                                     ranked_highlight=still_exists and local.ranked_highlight)
                updated[record.id] = record
            self._clips = updated
            try:
                if budget and self._used_bytes_locked() > max(budget, current_bytes):
                    raise ClipBudgetFull()
                self._save_locked()
            except OSError:
                self._clips = previous
                raise

    def _match_candidates(self, match_id: str) -> list[Clip]:
        return [clip for clip in self._clips.values() if clip.match_id == match_id
                and clip.ranked_highlight and not (clip.favorite or clip.deleted or clip.collections)]

    def would_keep_highlight(self, match_id: str, kills: int, limit: int) -> bool:
        with self._lock:
            candidates = self._match_candidates(match_id)
            return len(candidates) < limit or kills > sorted((c.kills for c in candidates), reverse=True)[limit - 1]

    def add_ranked(self, clip: Clip, limit: int, budget: int = 0) -> None:
        with self._lock:
            candidates = [*self._match_candidates(clip.match_id), clip]
            kept = sorted(candidates, key=lambda c: (-c.kills, c.created, c.id))[:limit]
            if clip not in kept:
                raise HighlightNotKept()
            retired = [candidate for candidate in candidates if candidate not in kept]
            retired_ids = {removed.id for removed in retired}
            previous = self._clips
            self._clips = {key: value for key, value in previous.items() if key not in retired_ids}
            self._clips[clip.id] = replace(clip, ranked_highlight=True)
            try:
                if budget and self._used_bytes_locked() > budget:
                    raise ClipBudgetFull()
                self._save_locked()
            except OSError:
                self._clips = previous
                raise
            live_files = {Path(c.path) for c in self._clips.values()}
            for old in retired:
                old_path = Path(old.path)
                try:
                    if old_path not in live_files:
                        old_path.unlink(missing_ok=True)
                    if old.thumb:
                        (paths.thumbs_dir() / Path(old.thumb).name).unlink(missing_ok=True)
                except OSError as exc:
                    log(f"Could not remove a replaced highlight: {exc}")

    def update(self, clip_id: str, **fields: Any) -> Clip | None:
        with self._lock:
            c = self._clips.get(clip_id)
            if c is None or c.deleted:
                return None
            updated = replace(c, **{key: value for key, value in fields.items() if key in Clip.__dataclass_fields__})
            self._clips[clip_id] = updated
            try:
                self._save_locked()
            except OSError:
                self._clips[clip_id] = c
                raise
            return updated

    def set_upload_status(self, clip_id: str, target: str, status: str) -> None:
        with self._lock:
            c = self._clips.get(clip_id)
            if c is not None:
                c.uploads[target] = status
                self._save_locked()

    def _used_bytes_locked(self, exclude: str = "") -> int:
        total = 0
        seen = set()
        for clip in self._clips.values():
            path = Path(clip.path)
            if clip.id == exclude or path in seen:
                continue
            seen.add(path)
            try:
                total += path.stat().st_size
            except FileNotFoundError:
                continue
        return total

    def used_bytes(self) -> int:
        with self._lock:
            return self._used_bytes_locked()

    def set_deleted(self, clip_id: str, deleted: bool) -> bool:
        with self._lock:
            clip = self._clips.get(clip_id)
            if not clip or clip.deleted == deleted:
                return False
            if deleted and clip.favorite:
                raise ValueError("Remove this clip from Favorites before deleting it.")
            self._clips[clip_id] = replace(clip, deleted=deleted)
            try:
                self._save_locked()
            except OSError:
                self._clips[clip_id] = clip
                raise
            return True

    def remove(self, clip_id: str, delete_file: bool = False, *, from_trash: bool = False) -> bool:
        with self._lock:
            clip = self._clips.get(clip_id)
            if not clip or clip.deleted != from_trash:
                return False
            if clip.favorite:
                raise ValueError("Remove this clip from Favorites before deleting it.")
            path = Path(clip.path)
            shared = any(c.id != clip_id and Path(c.path) == path for c in self._clips.values())
            if delete_file and not shared:
                path.unlink(missing_ok=True)
            del self._clips[clip_id]
            try:
                self._save_locked()
            except OSError:
                self._clips[clip_id] = clip
                raise
        if delete_file:
            if clip.thumb:
                try:
                    (paths.thumbs_dir() / Path(clip.thumb).name).unlink(missing_ok=True)
                except OSError as exc:
                    log(f"Could not remove the clip thumbnail: {exc}")
        return True

    def relink(self, old_folder: Path, new_folder: Path) -> int:
        with self._lock:
            original = self._clips
            updated = original.copy()
            occupied = {Path(c.path).resolve() for c in original.values() if c.exists()}
            count = 0
            for clip in original.values():
                source = Path(clip.path)
                if clip.exists() or not source.is_absolute():
                    continue
                source = source.resolve()
                if not source.is_relative_to(old_folder):
                    continue
                target = (new_folder / source.relative_to(old_folder)).resolve()
                if (not target.is_relative_to(new_folder) or target in occupied
                        or target.suffix.lower() not in {".mp4", ".mkv", ".mov"} or not target.is_file()):
                    continue
                updated[clip.id] = replace(clip, path=str(target), ranked_highlight=False)
                occupied.add(target)
                count += 1
            if count:
                self._clips = updated
                try:
                    self._save_locked()
                except OSError:
                    self._clips = original
                    raise
            return count

    def list(self, *, deleted: bool = False) -> list[Clip]:
        """Newest first."""
        with self._lock:
            return sorted((c for c in self._clips.values() if c.deleted == deleted),
                          key=lambda c: c.created, reverse=True)
