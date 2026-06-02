"""Pluggable upload targets.

Each uploader implements ``Uploader`` and is constructed from its slice of the
config. ``build_enabled(cfg)`` returns the ones the user has switched on, in a
deterministic order. The engine and the dashboard's "re-share" button both fan a
clip out through this same list, so adding a target means adding one module here.
"""
from __future__ import annotations

from ..config import Config
from .base import Uploader
from .gallery import GalleryUploader
from .telegram import TelegramUploader
from .discord import DiscordUploader
from .youtube import YouTubeUploader

# name -> (config key, class)
REGISTRY: list[tuple[str, type[Uploader]]] = [
    ("gallery", GalleryUploader),
    ("telegram", TelegramUploader),
    ("discord", DiscordUploader),
    ("youtube", YouTubeUploader),
]


def build_enabled(cfg: Config) -> list[Uploader]:
    out: list[Uploader] = []
    for name, cls in REGISTRY:
        if cfg.get(f"uploads.{name}.enabled"):
            out.append(cls(cfg))
    return out
