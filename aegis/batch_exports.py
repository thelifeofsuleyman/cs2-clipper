"""Persistent, local sharing copies prepared during breaks in CS2."""
from __future__ import annotations

import copy
import json
import re
import threading
import uuid
from pathlib import Path

from . import media, paths
from .log import log

LIMITS_MB = (10, 25)
VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov"}
MAX_CLIPS = 12
_JOB_ID = re.compile(r"[a-f0-9]{32}")


class BatchExports:
    def __init__(self, cfg, catalog, can_export, media_lock):
        self.cfg = cfg
        self.catalog = catalog
        self.can_export = can_export
        self._media_lock = media_lock
        self._root = paths.data_root() / "exports"
        self._lock = threading.Lock()
        self._worker = None
        self._working = None
        self._wake = threading.Event()
        self._jobs = {}
        for info in self._root.glob("*/batch.json"):
            if not _JOB_ID.fullmatch(info.parent.name):
                continue
            try:
                job = json.loads(info.read_text(encoding="utf-8"))
                if job["id"] == info.parent.name and job["max_mb"] in LIMITS_MB and isinstance(job["items"], list):
                    self._jobs[job["id"]] = job
            except (OSError, ValueError, TypeError, KeyError):
                log("Skipped an unreadable batch export record.")
        with self._lock:
            self._start_locked()

    def list(self) -> list[dict]:
        with self._lock:
            jobs = list(reversed(self._jobs.values()))
            result = copy.deepcopy(jobs)
            if self._working:
                job_id, index = self._working
                for job in result:
                    if job["id"] == job_id:
                        job["items"][index]["state"] = "working"
        return result

    def add(self, clip_ids: list[str], limit: int) -> dict:
        clips = [self.catalog.get(clip_id) for clip_id in clip_ids]
        if any(not c or not c.match_id or not c.exists() for c in clips):
            raise ValueError("Choose available clips from Matches.")
        job = {"id": uuid.uuid4().hex, "max_mb": limit, "items": [
            {"clip_id": c.id, "title": c.title or Path(c.path).stem, "state": "queued"} for c in clips
        ]}
        with self._lock:
            self._write(job)
            self._jobs[job["id"]] = job
            self._start_locked()
            self._wake.set()
            return copy.deepcopy(job)

    def _start_locked(self):
        if self._worker is None and self._next_locked():
            self._worker = threading.Thread(target=self._run, name="aegis-batch-exports", daemon=True)
            self._worker.start()

    def _write(self, job: dict):
        directory = self._root / job["id"]
        directory.mkdir(parents=True, exist_ok=True)
        paths.atomic_write_text(directory / "batch.json", json.dumps(job))

    def _next_locked(self):
        for job in self._jobs.values():
            for index, item in enumerate(job["items"]):
                if item["state"] == "queued":
                    return job, index
        return None

    def _run(self):
        while True:
            with self._lock:
                if self._next_locked() is None:
                    self._worker = None
                    return
            if not self.can_export() or not self._media_lock.acquire(blocking=False):
                self._wake.wait(2)
                self._wake.clear()
                continue
            try:
                with self._lock:
                    next_item = self._next_locked()
                    if next_item is None:
                        continue
                    job, index = next_item
                    self._working = job["id"], index
                item = job["items"][index]
                try:
                    prepared = self._prepare(job, index, item["clip_id"])
                    result = {"state": "ready", **prepared} if prepared else {
                        "state": "error", "error": "Could not prepare this clip within the size limit.",
                    }
                except media.ExportPaused:
                    continue
                except (OSError, ValueError) as exc:
                    log(f"Batch export failed: {exc}")
                    result = {"state": "error",
                              "error": "The export drive is full." if isinstance(exc, OSError) and paths.disk_full(exc)
                              else "The clip or export folder is unavailable."}
                except Exception as exc:
                    log(f"Batch export failed: {exc}")
                    result = {"state": "error", "error": "Could not prepare this clip. Check Activity."}
                with self._lock:
                    item.update(result)
                    try:
                        self._write(job)
                    except OSError as exc:
                        log(f"Could not save the batch export record: {exc}")
            finally:
                with self._lock:
                    self._working = None
                self._media_lock.release()

    def _prepare(self, job: dict, index: int, clip_id: str) -> dict | None:
        clip = self.catalog.get(clip_id)
        source = Path(clip.path) if clip else None
        if source is None or source.suffix.lower() not in VIDEO_SUFFIXES or not source.is_file():
            raise FileNotFoundError("Original clip unavailable")
        limit = job["max_mb"] * 1_000_000
        directory = self._root / job["id"]
        if not self.can_export():
            raise media.ExportPaused
        with source.open("rb") as original:
            data = original.read(limit + 1) if source.stat().st_size <= limit else b""
        copy_original = 0 < len(data) <= limit
        suffix = source.suffix.lower() if copy_original else ".mp4"
        staged = directory / f".{index}-pending{suffix}"
        try:
            if copy_original:
                staged.write_bytes(data)
            else:
                ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
                if not media.reencode_to_fit(ffmpeg, source, staged, limit, pause=lambda: not self.can_export()):
                    return None
            if not self.can_export():
                raise media.ExportPaused
            size = staged.stat().st_size
            if not 0 < size <= limit:
                return None
            staged.replace(directory / f"{index}{suffix}")
        finally:
            staged.unlink(missing_ok=True)
        return {"suffix": suffix, "bytes": size}

    def download(self, job_id: str, index: int) -> tuple[Path, str] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not 0 <= index < len(job["items"]):
                return None
            item = job["items"][index]
            if item["state"] != "ready" or item["suffix"] not in VIDEO_SUFFIXES:
                return None
            file = self._root / job_id / f"{index}{item['suffix']}"
            title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", item["title"]).strip(" .") or "Clip"
            return file, f"{title[:200]}-share{item['suffix']}"

    def remove(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            if self._working and self._working[0] == job_id:
                raise ValueError("Wait for the current clip export to finish.")
            directory = self._root / job_id
            # Batch-owned files use an index and a known media extension.
            for index, _ in enumerate(self._jobs[job_id]["items"]):
                for suffix in VIDEO_SUFFIXES:
                    (directory / f"{index}{suffix}").unlink(missing_ok=True)
                    (directory / f".{index}-pending{suffix}").unlink(missing_ok=True)
            (directory / "batch.json").unlink(missing_ok=True)
            del self._jobs[job_id]
            try:
                directory.rmdir()
            except OSError:
                pass
            return True
