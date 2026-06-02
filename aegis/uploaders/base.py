"""Uploader interface.

Implementations should never raise: return an ``UploadResult`` with ``ok=False``
and a short message instead, so one failing target can't break the others or the
clip pipeline. ``send`` receives the clip file and a human caption/title.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..config import Config


@dataclass
class UploadResult:
    ok: bool
    detail: str = ""

    def status(self) -> str:
        return "ok" if self.ok else f"error: {self.detail}"[:120]


class Uploader(ABC):
    #: stable key, matches the config slice and catalog upload-status key
    name: str = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def send(self, clip: Path, caption: str) -> UploadResult:
        ...
