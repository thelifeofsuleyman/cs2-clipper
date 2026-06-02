"""Capture engine — GSI listener, debounce, and the clip pipeline.

This is the heart carried over from the original clipper, now wired to the
config/catalog/uploader subsystems. Flow per streak:

  GSI ticks -> handle_payload() updates kill state under a lock
            -> schedule_save() (re)arms a debounce Timer on every new kill
            -> save_clip() fires when the timer expires:
                 OBS.save_replay_buffer() -> wait_for_new_clip()
                 -> catalog a Clip (thumbnail, size, duration)
                 -> fan out to every enabled uploader

Kill detection is delta-based: CS2 GSI reports cumulative kills, so we diff
against the previous tick. A decrease means a new match (counter reset) and is
swallowed; the -1 sentinel means "uninitialised", so connecting mid-match syncs
state without firing a stray clip.
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from . import media, uploaders
from .clips import Catalog, Clip
from .config import Config
from .log import log
from .obs_client import ObsClient

KILL_LABELS = {1: "Kill", 2: "Double tap", 3: "TRIPLE", 4: "QUAD", 5: "ACE"}


def format_caption(kills: int, map_name: str, round_n: int, side: str) -> str:
    label = KILL_LABELS.get(kills, f"{kills}K")
    parts = [label, f"on {map_name}"]
    if round_n > 0:
        parts.append(f"(round {round_n}, {side}-side)")
    return " ".join(parts)


class Engine:
    def __init__(self, cfg: Config, catalog: Catalog):
        self.cfg = cfg
        self.catalog = catalog
        self.obs = ObsClient(
            cfg.get("obs.host"), int(cfg.get("obs.port")), cfg.get("obs.password", "")
        )
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._state = {
            "last_match_kills": -1,
            "pending_kills": 0,
            "map_name": "unknown",
            "round_n": 0,
            "side": "?",
        }

    # ───────── GSI ingestion ─────────
    def handle_payload(self, p: dict) -> None:
        player = p.get("player") or {}
        match_stats = player.get("match_stats") or {}
        map_obj = p.get("map") or {}

        current_kills = int(match_stats.get("kills", 0))
        map_name = map_obj.get("name", "unknown")
        round_n = int(map_obj.get("round", 0))
        team = (player.get("team") or "?").upper()

        with self._lock:
            prev = self._state["last_match_kills"]
            if prev == -1 or current_kills < prev:
                if prev != -1:
                    log(f"New match / reset (kills {prev} -> {current_kills})")
                self._state.update(last_match_kills=current_kills, pending_kills=0)
                return

            diff = current_kills - prev
            self._state["last_match_kills"] = current_kills
            if diff <= 0:
                return

            self._state["pending_kills"] += diff
            self._state.update(map_name=map_name, round_n=round_n, side=team)
            log(f"Kill +{diff} (pending {self._state['pending_kills']}) "
                f"on {map_name} round {round_n}")
            self._arm_timer()

    def _arm_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        t = threading.Timer(float(self.cfg.get("engine.debounce_sec")), self._save_clip)
        t.daemon = True
        self._timer = t
        t.start()

    # ───────── status for the dashboard ─────────
    def status(self) -> dict:
        with self._lock:
            pending = self._state["pending_kills"]
        return {
            "obs_connected": self.obs.connected(),
            "replay_buffer_active": self.obs.replay_buffer_active(),
            "pending_kills": pending,
            "enabled_targets": [
                name for name, _ in uploaders.REGISTRY
                if self.cfg.get(f"uploads.{name}.enabled")
            ],
        }

    # ───────── clip pipeline ─────────
    def _save_clip(self) -> None:
        with self._lock:
            kills = self._state["pending_kills"]
            map_name = self._state["map_name"]
            round_n = self._state["round_n"]
            side = self._state["side"]
            self._state["pending_kills"] = 0

        if kills < int(self.cfg.get("engine.min_kills")):
            return

        log(f"Saving replay for {kills} kill(s)")
        if not self.obs.save_replay_buffer():
            log("OBS not reachable / save rejected — clip not saved")
            return

        clip_path = self._wait_for_new_clip(float(self.cfg.get("engine.clip_wait_sec")))
        if clip_path is None:
            log("No new clip appeared — is the Replay Buffer running in OBS?")
            return

        clip = self._catalog_clip(clip_path, kills, map_name, round_n, side)
        caption = format_caption(kills, map_name, round_n, side)
        self.fan_out(clip, caption)

    def _wait_for_new_clip(self, timeout: float) -> Path | None:
        replay_dir = Path(self.cfg.get("obs.replay_dir") or (Path.home() / "Videos"))
        start = time.time()
        deadline = start + timeout
        while time.time() < deadline:
            time.sleep(0.5)
            try:
                candidates = [
                    f for f in replay_dir.iterdir()
                    if f.is_file()
                    and f.suffix.lower() in (".mp4", ".mkv", ".mov")
                    and f.stat().st_mtime >= start - 1
                ]
            except FileNotFoundError:
                log(f"OBS replay dir not found: {replay_dir}")
                return None
            if candidates:
                latest = max(candidates, key=lambda f: f.stat().st_mtime)
                return self._await_complete(latest)
        return None

    @staticmethod
    def _await_complete(f: Path) -> Path:
        """Wait until the file size stops growing (OBS finished writing)."""
        prev = -1
        for _ in range(12):
            size = f.stat().st_size
            if size > 0 and size == prev:
                return f
            prev = size
            time.sleep(0.3)
        return f

    def _catalog_clip(self, path: Path, kills, map_name, round_n, side) -> Clip:
        cid = f"{int(path.stat().st_mtime)}_{uuid.uuid4().hex[:6]}"
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        thumb = media.make_thumbnail(ffmpeg, path, cid)
        clip = Clip(
            id=cid,
            path=str(path),
            created=path.stat().st_mtime,
            kills=kills,
            map_name=map_name,
            round_n=round_n,
            side=side,
            title=format_caption(kills, map_name, round_n, side),
            size_mb=round(path.stat().st_size / (1024 * 1024), 1),
            duration=round(media.probe_duration(ffmpeg, path), 1) if ffmpeg else 0.0,
            thumb=thumb.name if thumb else "",
        )
        self.catalog.add(clip)
        log(f"Cataloged clip {cid} ({clip.size_mb} MB)")
        return clip

    def fan_out(self, clip: Clip, caption: str) -> dict[str, str]:
        """Send a clip to every enabled uploader; record per-target status."""
        path = Path(clip.path)
        results: dict[str, str] = {}
        for up in uploaders.build_enabled(self.cfg):
            if up.name == "gallery":
                self.catalog.set_upload_status(clip.id, "gallery", "ok")
                results["gallery"] = "ok"
                continue
            log(f"Uploading {path.name} -> {up.name}: '{caption}'")
            res = up.send(path, caption)
            self.catalog.set_upload_status(clip.id, up.name, res.status())
            results[up.name] = res.status()
            log(f"{up.name}: {res.status()}")
        return results

    def build_montage(self, clip_ids: list[str]) -> Path | None:
        """Stitch selected clips (newest-first order) into one montage file."""
        from . import paths
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        clips = [self.catalog.get(cid) for cid in clip_ids]
        paths_in = [Path(c.path) for c in clips if c and c.exists()]
        if not paths_in:
            return None
        out = paths.montages_dir() / f"montage_{int(time.time())}.mp4"
        music = self.cfg.get("montage.music_path") or ""
        return media.build_montage(
            ffmpeg, paths_in, out,
            music=Path(music) if music and Path(music).exists() else None,
            vertical=bool(self.cfg.get("montage.vertical_export")),
        )
