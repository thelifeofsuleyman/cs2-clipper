"""Fetch a player's Steam avatar for clip intros.

Uses the public Steam Community profile XML — no API key required:
  https://steamcommunity.com/profiles/<steamid64>?xml=1
exposes an <avatarFull> image URL. Avatars are cached on disk by SteamID, so we
hit the network at most once per player. Every failure degrades to None so the
clip intro simply omits the picture.
"""
from __future__ import annotations

import re
from pathlib import Path

import requests

from . import paths
from .log import log

_AVATAR_RE = re.compile(r"<avatarFull><!\[CDATA\[(.*?)\]\]></avatarFull>")


def fetch_avatar(steamid: str) -> Path | None:
    if not steamid or not steamid.isdigit():
        return None
    cache = paths.avatars_dir() / f"{steamid}.png"
    if cache.exists() and cache.stat().st_size > 0:
        return cache
    try:
        xml = requests.get(
            f"https://steamcommunity.com/profiles/{steamid}?xml=1", timeout=8
        ).text
        m = _AVATAR_RE.search(xml)
        if not m:
            return None
        img = requests.get(m.group(1), timeout=8).content
        if not img:
            return None
        cache.write_bytes(img)
        return cache
    except Exception as e:
        log(f"Avatar fetch failed for {steamid}: {e}")
        return None
