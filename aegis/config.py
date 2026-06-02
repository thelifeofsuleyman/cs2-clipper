"""Settings store — a single JSON file the GUI/wizard and engine both read.

Why JSON instead of the old ``.env``: the setup wizard and dashboard need to
*write* settings back, and nested groups (per-uploader credentials) are awkward
as flat env vars. ``Config`` is a thin dict wrapper with dotted-path access,
sane defaults, and a one-time migration that imports an existing ``.env`` so
upgrading users keep their Telegram/OBS setup.

Load order on first run:
  1. start from DEFAULTS
  2. if config.json is missing, try to import legacy .env
  3. auto-detect OBS replay dir / CS2 cfg dir if still unset
  4. persist
"""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

from . import paths
from .log import log

DEFAULTS: dict[str, Any] = {
    "first_run": True,
    "engine": {
        "debounce_sec": 7.0,     # seconds of no-kill before a streak is clipped
        "min_kills": 1,          # 2 = skip solo kills
        "clip_wait_sec": 8.0,    # how long to wait for OBS to finish writing
        "gsi_port": 3000,        # CS2 GSI POST target (matches the .cfg)
    },
    "obs": {
        "host": "localhost",
        "port": 4455,
        "password": "",
        "replay_dir": "",        # OBS Settings -> Output -> Recording Path
    },
    "uploads": {
        "gallery":  {"enabled": True},   # always keep a local copy + catalog entry
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "discord":  {"enabled": False, "webhook_url": "", "max_mb": 25},
        "youtube":  {"enabled": False, "client_secrets": "", "privacy": "unlisted"},
    },
    "montage": {
        "music_path": "",
        "vertical_export": False,   # also render a 9:16 mobile cut
        "max_clips": 12,
    },
    "ffmpeg_path": "",  # blank = look on PATH / bundled
    "update": {
        "repo": "OWNER/REPO",   # GitHub slug to check Releases against; set per build
        "auto_check": True,     # check once on startup and surface a banner
    },
}


def _deep_merge(base: dict, over: dict) -> dict:
    """Overlay ``over`` onto a copy of ``base``, recursing into nested dicts."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data: dict[str, Any]):
        self._data = data
        self._lock = threading.Lock()

    # ---- dotted access: cfg.get("obs.port") ----
    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        with self._lock:
            node = self._data
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value

    def update(self, patch: dict[str, Any]) -> None:
        """Merge a nested patch dict (used by the wizard form handler)."""
        with self._lock:
            self._data = _deep_merge(self._data, patch)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def save(self) -> None:
        with self._lock:
            paths.config_file().write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )


# ───────── loading / migration / detection ─────────
def load() -> Config:
    f = paths.config_file()
    if f.exists():
        try:
            data = _deep_merge(DEFAULTS, json.loads(f.read_text(encoding="utf-8")))
            return Config(data)
        except Exception as e:
            log(f"config.json unreadable ({e}); starting from defaults")

    data = copy.deepcopy(DEFAULTS)
    _migrate_env(data)
    _autodetect(data)
    cfg = Config(data)
    cfg.save()
    return cfg


def _migrate_env(data: dict) -> None:
    """Import a legacy .env from the repo root, if present."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    vals: dict[str, str] = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        vals[k.strip()] = v.strip()
    if not vals:
        return

    log("Importing settings from legacy .env")
    e = data["engine"]
    e["debounce_sec"] = float(vals.get("DEBOUNCE_SEC", e["debounce_sec"]))
    e["min_kills"] = int(vals.get("MIN_KILLS", e["min_kills"]))
    e["clip_wait_sec"] = float(vals.get("CLIP_WAIT_SEC", e["clip_wait_sec"]))
    e["gsi_port"] = int(vals.get("GSI_PORT", e["gsi_port"]))
    o = data["obs"]
    o["host"] = vals.get("OBS_HOST", o["host"])
    o["port"] = int(vals.get("OBS_PORT", o["port"]))
    o["password"] = vals.get("OBS_PASSWORD", o["password"])
    o["replay_dir"] = vals.get("OBS_REPLAY_DIR", o["replay_dir"])
    tg = data["uploads"]["telegram"]
    if vals.get("TG_BOT_TOKEN") and vals.get("TG_CHAT_ID"):
        tg.update(enabled=True, bot_token=vals["TG_BOT_TOKEN"], chat_id=vals["TG_CHAT_ID"])


def _autodetect(data: dict) -> None:
    """Best-effort discovery so the wizard arrives pre-filled."""
    if not data["obs"]["replay_dir"]:
        guess = detect_obs_replay_dir()
        if guess:
            data["obs"]["replay_dir"] = str(guess)


def detect_obs_replay_dir() -> Path | None:
    """Read OBS's own recording path from its profile .ini, else fall back."""
    appdata = os.getenv("APPDATA")
    if appdata:
        profiles = Path(appdata) / "obs-studio" / "basic" / "profiles"
        if profiles.is_dir():
            for ini in profiles.glob("*/basic.ini"):
                try:
                    for line in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if line.startswith("RecRecPath=") or line.startswith("FilePath="):
                            p = Path(line.split("=", 1)[1].strip())
                            if p.is_dir():
                                return p
                except Exception:
                    continue
    vids = Path.home() / "Videos"
    return vids if vids.is_dir() else None


def detect_cs2_cfg_dir() -> Path | None:
    """Locate Counter-Strike's csgo\\cfg folder across common Steam library roots."""
    rel = Path("steamapps/common/Counter-Strike Global Offensive/game/csgo/cfg")
    candidates = [
        Path(r"C:\Program Files (x86)\Steam") / rel,
        Path(r"C:\Program Files\Steam") / rel,
    ]
    for drive in "DEFGH":
        candidates.append(Path(f"{drive}:\\SteamLibrary") / rel)
        candidates.append(Path(f"{drive}:\\Steam") / rel)
    for c in candidates:
        if c.is_dir():
            return c
    return None
