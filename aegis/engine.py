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

import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import media, paths, polish, uploaders
from .clips import Catalog, Clip
from .config import Config
from .log import log
from .recorder import make_recorder

KILL_LABELS = {1: "Kill", 2: "Double tap", 3: "TRIPLE", 4: "QUAD", 5: "ACE"}


def kill_basename(map_name: str, kills: int) -> str:
    """A human, sortable filename stem like 'mirage_4K' / 'dust2_1K' / 'inferno_ACE'
    so clips are identifiable on disk by map + kill count."""
    m = re.sub(r"^(de|cs|ar|dz|gd)_", "", (map_name or "clip").lower())
    m = re.sub(r"[^a-z0-9]+", "", m) or "clip"
    label = "ACE" if kills >= 5 else f"{kills}K"
    return f"{m}_{label}"


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
        self.recorder = make_recorder(cfg)
        self._lock = threading.Lock()
        self._rec_lock = threading.Lock()   # serializes recorder start/stop/restart
        self._timer: threading.Timer | None = None
        self._state = {
            "last_match_kills": -1,
            "pending_kills": 0,
            "map_name": "unknown",
            "round_n": 0,
            "side": "?",
            "steam_name": "",
            "steam_id": "",
        }

    # ───────── GSI ingestion ─────────
    def handle_payload(self, p: dict) -> None:
        player = p.get("player") or {}
        match_stats = player.get("match_stats") or {}
        map_obj = p.get("map") or {}

        provider = p.get("provider") or {}
        current_kills = int(match_stats.get("kills", 0))
        map_name = map_obj.get("name", "unknown")
        round_n = int(map_obj.get("round", 0))
        team = (player.get("team") or "?").upper()
        steam_name = player.get("name") or ""
        steam_id = str(player.get("steamid") or provider.get("steamid") or "")

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
            self._state.update(map_name=map_name, round_n=round_n, side=team,
                               steam_name=steam_name, steam_id=steam_id)
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

    # ───────── recorder lifecycle ─────────
    def start_recording(self) -> None:
        with self._rec_lock:
            self.recorder.start()

    def stop_recording(self) -> None:
        with self._rec_lock:
            self.recorder.stop()

    def restart_recording(self) -> None:
        """Rebuild the recorder (backend/quality may have changed) and restart it.
        Called after the wizard finishes or recording settings change. The lock
        serializes overlapping restarts (e.g. two concurrent config saves) so we
        never leak a second capture process."""
        with self._rec_lock:
            self.recorder.stop()                 # synchronous: old ffmpeg is gone
            self.recorder = make_recorder(self.cfg)
            self.recorder.start()

    # ───────── status for the dashboard ─────────
    def status(self) -> dict:
        with self._lock:
            pending = self._state["pending_kills"]
        rec = self.recorder.status()
        return {
            "recorder": rec,
            "capturing": rec.get("capturing", False),
            "pending_kills": pending,
            "enabled_targets": [
                name for name, _ in uploaders.REGISTRY
                if self.cfg.get(f"uploads.{name}.enabled")
            ],
        }

    # ───────── clip pipeline ─────────
    def _save_clip(self) -> None:
        # Snapshot the streak but DON'T zero it yet — only deduct once we know
        # the outcome, so a transient recorder failure doesn't silently discard a
        # real streak (and new kills arriving during the save are preserved).
        with self._lock:
            kills = self._state["pending_kills"]
            map_name = self._state["map_name"]
            round_n = self._state["round_n"]
            side = self._state["side"]
            steam_name = self._state["steam_name"]
            steam_id = self._state["steam_id"]

        if kills < int(self.cfg.get("engine.min_kills")):
            self._consume_pending(kills)         # below threshold: drop intentionally
            return

        log(f"Saving clip for {kills} kill(s)")
        raw_tmp = paths.clips_dir() / f".raw_{uuid.uuid4().hex[:8]}.mp4"
        clip_seconds = float(self.cfg.get("recording.clip_seconds", 30))
        clip_path = self.recorder.save(clip_seconds, raw_tmp)
        if clip_path is None:
            log("Recorder produced no clip — keeping the streak to retry on the next kill")
            return                                # keep pending_kills intact

        self._consume_pending(kills)             # success: deduct what we clipped

        # Produce a share-ready version (intro card + fades); fall back to raw.
        produced = clip_path
        try:
            polished = polish.polish_clip(self.cfg, clip_path, kills, map_name,
                                          steam_name, steam_id)
            if polished is not None:
                produced = polished
                try:
                    clip_path.unlink()           # drop the raw once we have the polished one
                except Exception:
                    pass
        except Exception as e:
            log(f"Polish step errored, keeping raw clip: {e}")

        # Give it a human filename: <map>_<kills>  e.g. mirage_4K, inferno_ACE
        final = self._finalize_clip(produced, map_name, kills)
        clip = self._catalog_clip(final, kills, map_name, round_n, side)
        caption = format_caption(kills, map_name, round_n, side)
        self.fan_out(clip, caption)

    def _finalize_clip(self, src: Path, map_name: str, kills: int) -> Path:
        """Move the produced clip to a unique '<map>_<kills>.mp4' name."""
        base = kill_basename(map_name, kills)
        d = paths.clips_dir()
        dest = d / f"{base}.mp4"
        n = 2
        while dest.exists():
            dest = d / f"{base}_{n}.mp4"
            n += 1
        try:
            shutil.move(str(src), str(dest))     # handles cross-volume (OBS dir)
            return dest
        except Exception as e:
            log(f"Could not rename clip to {dest.name}: {e}")
            return src

    def _consume_pending(self, kills: int) -> None:
        with self._lock:
            self._state["pending_kills"] = max(0, self._state["pending_kills"] - kills)

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

    def trigger_test_clip(self) -> dict:
        """Generate a synthetic clip, run it through polish (so the user previews
        the ACE intro card) + cataloging + uploads — all without playing CS2."""
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return {"ok": False, "detail": "ffmpeg not found — cannot make a test clip"}
        out = paths.clips_dir() / f"test_{int(time.time())}.mp4"
        if media.make_test_clip(ffmpeg, out, seconds=6) is None:
            return {"ok": False, "detail": "test clip generation failed"}

        name = self._state.get("steam_name") or "You"
        sid = self._state.get("steam_id") or ""
        try:
            polished = polish.polish_clip(self.cfg, out, 5, "de_dust2", name, sid)
            if polished is not None:
                try:
                    out.unlink()
                except Exception:
                    pass
                out = polished
        except Exception as e:
            log(f"Test clip polish errored: {e}")

        clip = self._catalog_clip(out, 5, "de_dust2", 0, "?")
        self.catalog.update(clip.id, title="Test clip (ACE preview)", tags=["test"])
        results = self.fan_out(clip, "Aegis Clipper test clip")
        return {"ok": True, "clip_id": clip.id, "results": results}

    def trigger_capture_test(self, seconds: int = 5) -> dict:
        """Record a few seconds of the REAL screen — proves ddagrab capture + the
        GPU encoder work on this machine, which the synthetic test can't."""
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return {"ok": False, "detail": "ffmpeg not found"}
        out = paths.clips_dir() / f"capture_test_{int(time.time())}.mp4"
        method = media.capture_screen_test(ffmpeg, out, seconds, self.cfg)
        if not method:
            return {"ok": False,
                    "detail": "screen capture failed with both ddagrab and gdigrab — see the Activity log"}
        # Remember the method that worked so the live recorder uses it too.
        if method != self.cfg.get("recording.capture"):
            self.cfg.set("recording.capture", method)
            self.cfg.save()
            self.restart_recording()
            log(f"Capture method switched to {method} (it's what works on this PC)")
        clip = self._catalog_clip(out, 0, "screen capture test", 0, "?")
        self.catalog.update(clip.id, title=f"Screen capture test ({method})", tags=["test"])
        return {"ok": True, "clip_id": clip.id, "method": method}

    def build_montage(self, clip_ids: list[str]) -> Path | None:
        """Stitch selected clips (newest-first order) into one montage file."""
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
            encode_args=media.quality_encode_args(ffmpeg, self.cfg),   # GPU when available
        )
