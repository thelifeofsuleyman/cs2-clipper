"""Capture engine — GSI listener, debounce, and the clip pipeline.

This is the heart carried over from the original clipper, now wired to the
config/catalog/uploader subsystems. Flow per streak:

  GSI ticks -> handle_payload() records kill times under a lock
            -> schedule_save() (re)arms a debounce Timer on every new kill
            -> save_clip() fires when the timer expires:
                 save the footage around each kill
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
from .recorder import HIGHLIGHT_HISTORY, highlight_ranges, make_recorder

KILL_LABELS = {1: "Kill", 2: "Double tap", 3: "TRIPLE", 4: "QUAD", 5: "ACE"}
COMPETITIVE_MODES = {"competitive", "premier", "wingman", "scrimcomp2v2"}


def kill_basename(map_name: str, kills: int) -> str:
    """A human, sortable filename stem like 'mirage_4K' / 'dust2_1K' / 'inferno_ACE'
    so clips are identifiable on disk by map + kill count."""
    m = re.sub(r"^(de|cs|ar|dz|gd)_", "", (map_name or "clip").lower())
    m = re.sub(r"[^a-z0-9]+", "", m) or "clip"
    label = "ACE" if kills == 5 else f"{kills}K"
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
        self.replay_hotkey_state = "off"
        self._lock = threading.Lock()
        self._rec_lock = threading.Lock()   # serializes recorder start/stop/restart
        self._save_lock = threading.Lock()
        self._file_lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._timer_token = None
        self._match_generation = 0
        self._last_gsi = 0.0
        self._save_attempts = 0
        self._save_successes = 0
        self._last_save_ms: int | None = None
        self._last_kill_at: float | None = None
        self._kill_events: list[tuple[float, int]] = []
        self._last_player = ""
        self._last_map = ""
        self._last_mode = ""
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
        if not isinstance(p, dict):
            return
        player = p.get("player") or {}
        map_obj = p.get("map") or {}
        provider = p.get("provider") or {}
        if not all(isinstance(obj, dict) for obj in (player, map_obj, provider)):
            return
        with self._lock:
            if provider or player:
                self._last_gsi = time.monotonic()

        owner = str(provider.get("steamid") or "")
        observed = str(player.get("steamid") or "")
        if owner and observed and owner != observed:
            return
        match_stats = player.get("match_stats") or {}
        current_kills = match_stats.get("kills") if isinstance(match_stats, dict) else None
        if type(current_kills) is not int or current_kills < 0:
            return
        map_name = str(map_obj.get("name") or "")
        mode = str(map_obj.get("mode") or "").strip().lower()
        round_value = map_obj.get("round", 0)
        round_n = round_value if type(round_value) is int else 0
        team = str(player.get("team") or "?").upper()
        steam_name = player.get("name") or ""
        steam_id = observed or owner

        with self._lock:
            if not owner and observed and self._last_player and observed != self._last_player:
                return
            prev = self._state["last_match_kills"]
            changed_match = ((map_name and self._last_map and map_name != self._last_map)
                             or (mode and self._last_mode and mode != self._last_mode)
                             or (steam_id and self._last_player and steam_id != self._last_player))
            self._last_map = map_name or self._last_map
            self._last_player = steam_id or self._last_player
            if prev == -1 or current_kills < prev or changed_match:
                if prev != -1:
                    log(f"New match / reset (kills {prev} -> {current_kills})")
                self._match_generation += 1
                if self._timer:
                    self._timer.cancel()
                self._timer_token = None
                self._last_kill_at = None
                self._kill_events.clear()
                self._last_mode = mode
                self._state.update(last_match_kills=current_kills, pending_kills=0)
                return

            diff = current_kills - prev
            self._state["last_match_kills"] = current_kills
            self._last_mode = mode or self._last_mode
            if diff <= 0 or not self._mode_allows_highlights(self._last_mode):
                return

            now = time.monotonic()
            if self._last_kill_at is not None and now - self._last_kill_at >= self._replay_window():
                if self._state["pending_kills"]:
                    log("Previous streak aged out of the replay buffer")
                    self._state["pending_kills"] = 0
                    self._kill_events.clear()
                    self._match_generation += 1
            self._last_kill_at = now
            self._kill_events.append((now, diff))
            self._state["pending_kills"] += diff
            self._state.update(map_name=self._last_map or "unknown", round_n=round_n, side=team,
                               steam_name=steam_name, steam_id=steam_id)
            log(f"Kill +{diff} (pending {self._state['pending_kills']}) "
                f"on {map_name} round {round_n}")
            self._arm_timer()

    def _arm_timer(self, delay: float | None = None) -> None:
        if self._timer is not None:
            self._timer.cancel()
        token = self._timer_token = object()
        if delay is None:
            delay = float(self.cfg.get("engine.debounce_sec"))
        t = threading.Timer(delay, lambda: self._save_clip(token))
        t.daemon = True
        self._timer = t
        t.start()

    def _mode_allows_highlights(self, mode: str) -> bool:
        setting = self.cfg.get("engine.highlight_modes", "no_deathmatch")
        if setting == "off":
            return False
        if setting == "competitive":
            return mode in COMPETITIVE_MODES
        return setting == "all" or mode != "deathmatch"

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
            last_gsi = self._last_gsi
            mode = self._last_mode
        rec = self.recorder.status()
        return {
            "recorder": rec,
            "capturing": rec.get("capturing", False),
            "pending_kills": pending,
            "automatic_highlights": self._mode_allows_highlights(mode),
            "replay_hotkey": self.replay_hotkey_state,
            "gsi_connected": bool(last_gsi and time.monotonic() - last_gsi < 25),
            "enabled_targets": [
                name for name, _ in uploaders.REGISTRY
                if self.cfg.get(f"uploads.{name}.enabled")
            ],
        }

    def replay_metrics(self) -> dict:
        with self._lock:
            return {"attempts": self._save_attempts, "saved": self._save_successes,
                    "last_save_ms": self._last_save_ms}

    def clips_dir(self) -> Path:
        return paths.clips_dir(self.cfg.get("storage.clips_dir", ""))

    def _record_replay(self, seconds: float, destination: Path,
                       ranges: list[tuple[float, float]] | None = None) -> Path | None:
        saved = None
        with self._rec_lock:
            started = time.monotonic()
            try:
                saved = self.recorder.save(seconds, destination, ranges)
                return saved
            finally:
                elapsed_ms = round((time.monotonic() - started) * 1000)
                with self._lock:
                    self._save_attempts += 1
                    self._save_successes += int(saved is not None)
                    self._last_save_ms = elapsed_ms

    # ───────── clip pipeline ─────────
    def _save_clip(self, token=None) -> None:
        with self._save_lock:
            saved = self._save_current_streak(token)
        if saved:
            self._publish_clip(*saved)

    def _save_current_streak(self, token) -> tuple | None:
        # Snapshot the streak but DON'T zero it yet — only deduct once we know
        # the outcome, so a transient recorder failure doesn't silently discard a
        # real streak (and new kills arriving during the save are preserved).
        with self._lock:
            if token is not None and token is not self._timer_token:
                return
            generation = self._match_generation
            last_kill = self._last_kill_at
            kills = self._state["pending_kills"]
            events = self._kill_events[:]
            mode = self._last_mode
            map_name = self._state["map_name"]
            round_n = self._state["round_n"]
            side = self._state["side"]
            steam_name = self._state["steam_name"]
            steam_id = self._state["steam_id"]

        if not self._mode_allows_highlights(mode) or kills < int(self.cfg.get("engine.min_kills")):
            self._consume_pending(kills, generation, len(events))
            return

        clip_seconds = self._replay_window()
        expires_at = (last_kill if last_kill is not None else time.monotonic()) + clip_seconds
        if time.monotonic() >= expires_at:
            log("Streak aged out of the replay buffer before it could be saved")
            self._consume_pending(kills, generation, len(events))
            return

        oldest = time.monotonic() - clip_seconds
        retained = [(stamp, count) for stamp, count in events if stamp >= oldest]
        recent_kills = sum(count for _, count in retained)
        if recent_kills < int(self.cfg.get("engine.min_kills")):
            self._consume_pending(kills, generation, len(events))
            return
        log(f"Saving highlight for {recent_kills} kill(s)")
        try:
            raw_tmp = self.clips_dir() / f".raw_{uuid.uuid4().hex[:8]}.mp4"
            clip_path = self._record_replay(clip_seconds, raw_tmp, highlight_ranges([stamp for stamp, _ in retained]))
        except Exception as e:
            log(f"Replay save failed: {e}")
            clip_path = None
        if clip_path is None:
            with self._lock:
                if generation == self._match_generation and token is self._timer_token:
                    # A fresh kill supersedes this retry and starts a new debounce.
                    self._arm_timer(max(0.0, min(2.0, expires_at - time.monotonic())))
                    log("Recorder produced no clip. Retrying while the streak is in the buffer.")
            return

        self._consume_pending(kills, generation, len(events))
        return clip_path, recent_kills, map_name, round_n, side, steam_name, steam_id

    def _replay_window(self) -> float:
        requested = float(self.cfg.get("recording.clip_seconds", 30))
        debounce = float(self.cfg.get("engine.debounce_sec"))
        segment = max(1, int(self.cfg.get("recording.segment_time", 2)))
        history = HIGHLIGHT_HISTORY if self.cfg.get("recording.backend") == "builtin" else 0
        return max(requested, history, debounce + 2 * segment)

    def _publish_clip(self, clip_path: Path, kills: int, map_name: str, round_n: int,
                      side: str, steam_name: str, steam_id: str) -> None:
        # Produce a share-ready version (intro card + fades); fall back to raw.
        produced = clip_path
        try:
            polished = None
            prioritize_fps = (self.cfg.get("recording.backend") == "builtin"
                              and self.cfg.get("recording.prioritize_game_fps", True))
            if not prioritize_fps:
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
        with self._file_lock:
            final = self._finalize_clip(produced, map_name, kills)
        clip = self._catalog_clip(final, kills, map_name, round_n, side)
        caption = format_caption(kills, map_name, round_n, side)
        self.fan_out(clip, caption)

    def _finalize_clip(self, src: Path, map_name: str, kills: int) -> Path:
        """Move the clip to a unique name, preserving its container extension."""
        base = kill_basename(map_name, kills)
        try:
            d = self.clips_dir()
            suffix = src.suffix
            dest = d / f"{base}{suffix}"
            n = 2
            while dest.exists():
                dest = d / f"{base}_{n}{suffix}"
                n += 1
            shutil.move(str(src), str(dest))     # handles cross-volume (OBS dir)
            return dest
        except Exception as e:
            log(f"Could not rename clip to {dest.name}: {e}")
            return src

    def _consume_pending(self, kills: int, generation: int, event_count: int) -> None:
        with self._lock:
            if generation == self._match_generation:
                del self._kill_events[:event_count]
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
        """Build and catalog a synthetic clip for local preview."""
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return {"ok": False, "detail": "ffmpeg not found — cannot make a test clip"}
        out = self.clips_dir() / f"test_{uuid.uuid4().hex[:10]}.mp4"
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
        return {"ok": True, "clip_id": clip.id}

    def save_replay(self) -> dict:
        out = self.clips_dir() / f"replay_{uuid.uuid4().hex[:10]}.mp4"
        captured = self._record_replay(float(self.cfg.get("recording.clip_seconds", 30)), out)
        if not captured:
            return {"ok": False, "detail": "Replay buffer is unavailable. Check capture status and Activity."}
        if self.cfg.get("storage.clips_dir") and captured.parent != out.parent:
            destination = out.with_suffix(captured.suffix)
            try:
                shutil.move(str(captured), str(destination))
                captured = destination
            except OSError as exc:
                log(f"Could not move the OBS replay to the clip folder: {exc}")
        clip = self._catalog_clip(captured, 0, "Manual replay", 0, "?")
        self.catalog.update(clip.id, title="Manual replay")
        return {"ok": True, "clip_id": clip.id}

    def trigger_capture_test(self, seconds: int = 5) -> dict:
        """Record a few seconds of the REAL screen — proves ddagrab capture + the
        GPU encoder work on this machine, which the synthetic test can't."""
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return {"ok": False, "detail": "ffmpeg not found"}
        out = self.clips_dir() / f"capture_test_{uuid.uuid4().hex[:10]}.mp4"
        method = media.capture_screen_test(ffmpeg, out, seconds, self.cfg)
        if not method:
            return {"ok": False,
                    "detail": "screen capture failed with both ddagrab and gdigrab — see the Activity log"}
        # Remember the method that worked so the live recorder uses it too.
        if self.cfg.get("recording.backend") == "builtin" and method != self.cfg.get("recording.capture"):
            self.cfg.set("recording.capture", method)
            self.cfg.save()
            if not self.cfg.get("first_run"):
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
        out = paths.montages_dir() / f"montage_{uuid.uuid4().hex[:10]}.mp4"
        music = self.cfg.get("montage.music_path") or ""
        return media.build_montage(
            ffmpeg, paths_in, out,
            music=Path(music) if music and Path(music).exists() else None,
            vertical=bool(self.cfg.get("montage.vertical_export")),
            encode_args=media.quality_encode_args(ffmpeg, self.cfg),   # GPU when available
        )
