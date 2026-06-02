"""Per-user data and config directories.

Everything Aegis writes at runtime lives under one root so an installed copy
keeps zero state next to the program files. On Windows that root is
``%APPDATA%\\AegisClipper``; elsewhere it falls back to ``~/.aegis-clipper``.

Set ``AEGIS_DATA_DIR`` to override (handy for dev — keep state inside the repo).
"""
from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    override = os.getenv("AEGIS_DATA_DIR")
    if override:
        root = Path(override)
    elif os.name == "nt" and os.getenv("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "AegisClipper"
    else:
        root = Path.home() / ".aegis-clipper"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sub(name: str) -> Path:
    p = data_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return data_root() / "config.json"


def catalog_file() -> Path:
    return data_root() / "clips.json"


def thumbs_dir() -> Path:
    return _sub("thumbnails")


def montages_dir() -> Path:
    return _sub("montages")


def logs_dir() -> Path:
    return _sub("logs")
