"""Local gallery 'uploader'.

A no-op sink that always succeeds — clips already live on disk and the catalog
already tracks them, so the gallery target just confirms the local copy is the
canonical one. It exists so the dashboard can show a consistent per-target status
row and so "gallery only" is a valid configuration (capture without sharing).
"""
from __future__ import annotations

from pathlib import Path

from .base import Uploader, UploadResult


class GalleryUploader(Uploader):
    name = "gallery"

    def send(self, clip: Path, caption: str) -> UploadResult:
        return UploadResult(clip.exists(), "" if clip.exists() else "file missing")
