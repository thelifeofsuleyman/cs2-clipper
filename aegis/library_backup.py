"""Portable clip backups. Archive entries never choose a restore destination."""
from __future__ import annotations

import json
import math
import re
import shutil
import uuid
from copy import deepcopy
from pathlib import Path
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from .batch_exports import VIDEO_SUFFIXES
from .clips import Catalog, Clip, ClipBudgetFull, collection_names

_CATALOG = "roundlatch-library.json"
_METADATA_LIMIT = 32 * 1024**2
_CLIP_ID = re.compile(r"[a-zA-Z0-9_-]{1,128}")
_INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_FIELDS = ("id", "created", "kills", "map_name", "round_n", "side", "title", "tags",
           "favorite", "size_mb", "duration", "match_id", "match_mode", "match_started",
           "kill_markers", "collections")


def backup_path(value: str) -> Path:
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("Enter a full path to a ZIP backup.")
    value = value.strip()
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != ".zip" or value.startswith(("\\\\?\\", "\\\\.\\")):
        raise ValueError("Enter a full path to a ZIP backup.")
    return path


def create_backup(catalog: Catalog, destination: Path, include_videos: bool) -> dict:
    clips = catalog.list()
    manifest = []
    videos = 0
    with destination.open("xb") as output:
        try:
            with ZipFile(output, "w", compression=ZIP_STORED) as archive:
                for index, clip in enumerate(clips):
                    source = Path(clip.path)
                    item = {key: deepcopy(getattr(clip, key)) for key in _FIELDS}
                    item["filename"] = source.name if source.suffix.lower() in VIDEO_SUFFIXES else f"clip-{index}.mp4"
                    if include_videos and source.is_file() and source.suffix.lower() in VIDEO_SUFFIXES:
                        item["video"] = f"videos/{index}{source.suffix.lower()}"
                        archive.write(source, item["video"])
                        videos += 1
                    manifest.append(item)
                metadata = json.dumps({"schema": 1, "clips": manifest}, ensure_ascii=False).encode("utf-8")
                if len(metadata) > _METADATA_LIMIT:
                    raise ValueError("The library is too large for a single backup.")
                archive.writestr(_CATALOG, metadata)
        except BaseException:
            output.close()
            destination.unlink(missing_ok=True)
            raise
    return {"clips": len(clips), "videos": videos}


def _valid_number(value) -> bool:
    return type(value) in (int, float) and 0 <= value < 1e15 and math.isfinite(value)


def _metadata(item: dict, index: int) -> tuple[dict, str, str | None]:
    if not isinstance(item, dict) or any(key not in item for key in _FIELDS):
        raise ValueError("This backup is missing clip metadata.")
    record = {key: item[key] for key in _FIELDS}
    filename = item.get("filename")
    video = item.get("video")
    if (not isinstance(filename, str) or len(filename) > 240 or _INVALID_NAME.search(filename)
            or Path(filename).suffix.lower() not in VIDEO_SUFFIXES
            or (video is not None and video != f"videos/{index}{Path(filename).suffix.lower()}")):
        raise ValueError("This backup contains an invalid video name.")
    if (not isinstance(record["id"], str) or not _CLIP_ID.fullmatch(record["id"])
            or any(not isinstance(record[key], str) or len(record[key]) > 512
                   for key in ("map_name", "side", "title", "match_id", "match_mode"))
            or any(not _valid_number(record[key]) for key in ("created", "size_mb", "duration", "match_started"))
            or any(type(record[key]) is not int or not 0 <= record[key] <= 100000 for key in ("kills", "round_n"))
            or type(record["favorite"]) is not bool):
        raise ValueError("This backup contains invalid clip metadata.")
    tags, markers = record["tags"], record["kill_markers"]
    if (not isinstance(tags, list) or any(not isinstance(tag, str) or len(tag) > 512 for tag in tags)
            or not isinstance(markers, list) or any(not isinstance(marker, dict) or not _valid_number(marker.get("time"))
               or any(type(marker.get(key)) is not int for key in ("round", "kills")) for marker in markers)):
        raise ValueError("This backup contains invalid clip labels or kill markers.")
    record["collections"] = collection_names(record["collections"])
    return record, filename, video


def restore_backup(catalog: Catalog, source: Path, folder: Path, budget: int) -> dict:
    copied: list[Path] = []
    try:
        with ZipFile(source) as archive:
            names = [entry.filename for entry in archive.infolist()]
            if len(names) != len(set(names)) or _CATALOG not in names:
                raise ValueError("Choose a valid RoundLatch library backup.")
            if archive.getinfo(_CATALOG).file_size > _METADATA_LIMIT:
                raise ValueError("This backup has too much metadata.")
            manifest = json.loads(archive.read(_CATALOG))
            if not isinstance(manifest, dict) or manifest.get("schema") != 1 or not isinstance(manifest.get("clips"), list):
                raise ValueError("This backup format is unsupported.")
            items = [_metadata(item, index) for index, item in enumerate(manifest["clips"])]
            if len({entry[0]["id"] for entry in items}) != len(items):
                raise ValueError("This backup contains duplicate clips.")
            records = []
            remaining = budget - catalog.used_bytes() if budget else None
            root = folder.resolve()
            for record, filename, video in items:
                local = catalog.get(record["id"], include_deleted=True)
                destination = (root / filename).resolve()
                if not destination.is_relative_to(root):
                    raise ValueError("A video path points outside the clip folder.")
                if local and local.exists():
                    destination = Path(local.path)
                elif video:
                    entry = archive.getinfo(video)
                    if entry.is_dir():
                        raise ValueError("A video is missing from this backup.")
                    if remaining is not None and entry.file_size > remaining:
                        raise ClipBudgetFull()
                    destination = root / f"restored-{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
                    with destination.open("xb") as output:
                        copied.append(destination)
                        with archive.open(entry) as embedded:
                            shutil.copyfileobj(embedded, output)
                    if remaining is not None:
                        remaining -= entry.file_size
                records.append(Clip(path=str(destination), **record))
        catalog.restore(records, budget)
        return {"clips": len(records), "videos": len(copied), "missing": sum(not clip.exists() for clip in records)}
    except BaseException as exc:
        for file in copied:
            file.unlink(missing_ok=True)
        if isinstance(exc, (BadZipFile, KeyError, UnicodeError, RuntimeError)):
            raise ValueError("The backup is incomplete or damaged.") from exc
        raise
