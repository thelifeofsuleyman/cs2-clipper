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
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from . import media, paths, polish, uploaders
from .clips import Catalog, Clip, ClipBudgetFull
from .config import Config
from .health import HealthMetrics
from .log import log
from .recorder import HIGHLIGHT_HISTORY, highlight_ranges, make_recorder
from .storage import StorageStatus

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


def playback_markers(events: list[tuple[float, int, int]],
                     spans: tuple[tuple[float, float], ...]) -> list[dict]:
    markers = []
    for stamp, count, round_n in events:
        elapsed = 0.0
        for start, end in spans:
            if start <= stamp < end:
                markers.append({"time": round(elapsed + stamp - start, 3),
                                "kills": count, "round": round_n})
                break
            elapsed += end - start
    return markers


class Engine:
    def __init__(self, cfg: Config, catalog: Catalog):
        self.cfg = cfg
        self.catalog = catalog
        self.health = HealthMetrics(cfg)
        self.recorder = make_recorder(cfg, self.health)
        self.replay_hotkey_state = "off"
        self.replay_receipt = None
        self._highlight_notice = None
        self.notify_replay = None
        self._storage_status = StorageStatus()
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
        self._kill_events: list[tuple[float, int, int]] = []
        self._recent_kills: list[tuple[float, int, int]] = []
        self._match: dict = {}
        self._match_observed_at = 0.0
        self._last_round: int | None = None
        self._last_phase = ""
        self._game_phase = ""
        self._game_phase_at = 0.0
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
        round_obj = p.get("round") or {}
        provider = p.get("provider") or {}
        if not all(isinstance(obj, dict) for obj in (player, map_obj, provider)):
            return
        with self._lock:
            if provider or player:
                self._last_gsi = time.monotonic()
                phase = map_obj.get("phase")
                if phase in ("warmup", "live", "halftime", "gameover", "intermission"):
                    self._game_phase = phase
                    self._game_phase_at = self._last_gsi
                elif not map_obj and player.get("activity") == "menu":
                    self._game_phase = "menu"
                    self._game_phase_at = self._last_gsi

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
        round_value = map_obj.get("round")
        round_n = round_value if type(round_value) is int and round_value >= 0 else None
        round_phase = round_obj.get("phase") if isinstance(round_obj, dict) else None
        phase = str(map_obj.get("phase") or "").lower()
        team = str(player.get("team") or "?").upper()
        steam_name = player.get("name") or ""
        steam_id = observed or owner

        with self._lock:
            if not owner and observed and self._last_player and observed != self._last_player:
                return
            prev = self._state["last_match_kills"]
            changed_match = ((map_name and self._last_map and map_name != self._last_map)
                             or (mode and self._last_mode and mode != self._last_mode)
                             or (steam_id and self._last_player and steam_id != self._last_player)
                             or (phase in ("warmup", "live") and self._last_phase in ("gameover", "intermission"))
                             or (round_n is not None and self._last_round is not None
                                 and round_n < self._last_round))
            reset = prev == -1 or current_kills < prev or changed_match
            self._last_map = map_name or self._last_map
            self._last_player = steam_id or self._last_player
            self._last_mode = mode or self._last_mode
            if reset or round_n is not None:
                self._last_round = round_n
            if reset or phase:
                self._last_phase = phase
            display_round = self._state["round_n"] if not reset else 0
            if self._last_round is not None:
                if self._last_mode in ("deathmatch", "gungameprogressive") or self._last_phase == "warmup":
                    display_round = 0
                elif round_n is not None:
                    ended = round_phase == "over" or self._last_phase in ("gameover", "intermission")
                    display_round = max(1, round_n + (0 if ended else 1))
            self._state.update(last_match_kills=current_kills, map_name=self._last_map or "unknown",
                               round_n=display_round, side=team, steam_name=steam_name,
                               steam_id=steam_id)
            now = time.monotonic()
            if reset or (not self._match and map_name):
                self._recent_kills.clear()
                self._match_observed_at = now
                self._match = ({"match_id": uuid.uuid4().hex, "match_mode": self._last_mode,
                                "match_started": time.time()} if self._last_map else {})
            elif self._match and mode:
                self._match["match_mode"] = mode
            if reset:
                self._highlight_notice = None
                if prev != -1:
                    log(f"New match / reset (kills {prev} -> {current_kills})")
                self._match_generation += 1
                if self._timer:
                    self._timer.cancel()
                self._timer_token = None
                self._last_kill_at = None
                self._kill_events.clear()
                self._state["pending_kills"] = 0
                return

            diff = current_kills - prev
            if diff <= 0:
                return
            event = (now, diff, self._state["round_n"])
            history_start = now - self._replay_window()
            self._recent_kills = [kill for kill in self._recent_kills if kill[0] >= history_start]
            self._recent_kills.append(event)
            if not self._mode_allows_highlights(self._last_mode):
                disabled = self.cfg.get("engine.highlight_modes") == "off"
                self._highlight_notice = {"state": "skipped", "message": "Kill detected. Automatic highlights are off." if disabled
                                          else "Kill detected. This match mode is excluded by your highlight settings."}
                return
            if self._last_kill_at is not None and now - self._last_kill_at >= self._replay_window():
                if self._state["pending_kills"]:
                    log("Previous streak aged out of the replay buffer")
                    self._state["pending_kills"] = 0
                    self._kill_events.clear()
                    self._match_generation += 1
            self._last_kill_at = now
            self._kill_events.append(event)
            self._state["pending_kills"] += diff
            self._highlight_notice = {"state": "detected", "message": "Kill detected. Waiting for the streak to end."}
            log(f"Kill +{diff} (pending {self._state['pending_kills']}) "
                f"on {map_name} round {round_n}")
            self._arm_timer()

    def _arm_timer(self, delay: float | None = None) -> None:
        if self._timer is not None:
            self._timer.cancel()
        token = self._timer_token = object()
        if delay is None:
            delay = float(self.cfg.get("engine.debounce_sec"))
            if self.cfg.get("recording.backend") == "obs" or self.cfg.get("engine.highlight_window") == "custom":
                delay = max(delay, self.cfg.highlight_padding()[1])
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
        self.health.flush()

    def restart_recording(self) -> None:
        """Rebuild the recorder (backend/quality may have changed) and restart it.
        Called after the wizard finishes or recording settings change. The lock
        serializes overlapping restarts (e.g. two concurrent config saves) so we
        never leak a second capture process."""
        with self._rec_lock:
            self.recorder.stop()                 # synchronous: old ffmpeg is gone
            self.recorder = make_recorder(self.cfg, self.health)
            self.recorder.start()

    # ───────── status for the dashboard ─────────
    def status(self) -> dict:
        with self._lock:
            pending = self._state["pending_kills"]
            last_gsi = self._last_gsi
            mode = self._last_mode
            highlight_notice = self._highlight_notice
        rec = self.recorder.status()
        return {
            "recorder": rec,
            "capturing": rec.get("capturing", False),
            "replay_available": rec.get("replay_available", rec.get("capturing", False)),
            "pending_kills": pending,
            "automatic_highlights": self._mode_allows_highlights(mode),
            "replay_hotkey": self.replay_hotkey_state,
            "replay_receipt": self.replay_receipt,
            "highlight_notice": highlight_notice,
            "verify_first_replay": bool(self.cfg.get("verify_first_replay")),
            "replay_shortcut": self.cfg.get("hotkeys.replay", "") if self.cfg.get("verify_first_replay") else "",
            "storage": self.storage_status(),
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

    def can_batch_export(self) -> bool:
        with self._lock:
            phase, observed = self._game_phase, self._game_phase_at
        if observed and time.monotonic() - observed < 25:
            return phase in ("gameover", "menu")
        if sys.platform != "win32":
            return True
        from .winprocess import is_running

        try:
            return not is_running("cs2.exe")
        except OSError:
            return False

    def storage_status(self) -> dict:
        folder = self.cfg.get("storage.clips_dir", "")
        if self.cfg.get("recording.backend") == "obs":
            buffer = Path(self.cfg.get("obs.replay_dir") or Path.home() / "Videos")
            return self._storage_status.status(folder or str(buffer), buffer)
        return self._storage_status.status(folder, self._storage_status.buffer)

    def _record_replay(self, seconds: float, destination: Path,
                       ranges: list[tuple[float, float]] | None = None
                       ) -> tuple[Path | None, tuple[tuple[float, float], ...]]:
        saved = None
        with self._rec_lock:
            started = time.monotonic()
            try:
                saved = self.recorder.save(seconds, destination, ranges)
                return saved, tuple(getattr(self.recorder, "last_saved_spans", ())) if saved else ()
            finally:
                elapsed_ms = round((time.monotonic() - started) * 1000)
                self.health.add(save_attempts=1, saves=int(saved is not None), save_ms=elapsed_ms)
                with self._lock:
                    self._save_attempts += 1
                    self._save_successes += int(saved is not None)
                    self._last_save_ms = elapsed_ms

    # ───────── clip pipeline ─────────
    def _save_clip(self, token=None) -> None:
        with self._save_lock:
            saved = self._save_current_streak(token)
        if saved:
            notice, generated, clip = saved
            try:
                self._publish_clip(*clip, generated=generated)
            except ClipBudgetFull as exc:
                self._finish_highlight_notice(notice, "skipped", str(exc))
            except Exception as exc:
                self.health.add(save_errors=1)
                log(f"Could not add the highlight to the library: {exc}")
                self._finish_highlight_notice(notice, "failed",
                                              "The highlight could not be added to the library. Check Activity.")
            else:
                self.health.add(clips_saved=1)
                self._finish_highlight_notice(notice, "saved", "Highlight saved to your clip library.")

    def _finish_highlight_notice(self, previous: dict | None, state: str, message: str) -> None:
        with self._lock:
            if self._highlight_notice is previous:
                self._highlight_notice = {"state": state, "message": message}

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
            match = self._match.copy()
            mode = self._last_mode
            map_name = self._state["map_name"]
            round_n = events[-1][2] if events else self._state["round_n"]
            side = self._state["side"]
            steam_name = self._state["steam_name"]
            steam_id = self._state["steam_id"]
            notice = self._highlight_notice

        minimum = int(self.cfg.get("engine.min_kills"))
        allowed = self._mode_allows_highlights(mode)
        if not allowed or kills < minimum:
            if kills:
                reason = (f"Skipped highlight. The streak was below your {minimum}-kill minimum."
                          if allowed else "Skipped highlight. This match mode is excluded.")
                self._finish_highlight_notice(notice, "skipped", reason)
            self._consume_pending(kills, generation, len(events))
            return

        clip_seconds = self._replay_window()
        expires_at = (last_kill if last_kill is not None else time.monotonic()) + clip_seconds
        if time.monotonic() >= expires_at:
            log("Streak aged out of the replay buffer before it could be saved")
            self._finish_highlight_notice(notice, "failed", "The highlight expired before the recorder could save it.")
            self._consume_pending(kills, generation, len(events))
            return

        oldest = time.monotonic() - clip_seconds
        retained = [event for event in events if event[0] >= oldest]
        recent_kills = sum(count for _, count, _ in retained)
        if recent_kills < minimum:
            self._finish_highlight_notice(notice, "skipped", "Too few kills were still in the replay buffer.")
            self._consume_pending(kills, generation, len(events))
            return
        log(f"Saving highlight for {recent_kills} kill(s)")
        try:
            self._check_clip_budget()
            raw_tmp = self.clips_dir() / f".raw_{uuid.uuid4().hex[:8]}.mp4"
            ranges = highlight_ranges([stamp for stamp, _, _ in retained], *self.cfg.highlight_padding())
            clip_path, spans = self._record_replay(clip_seconds, raw_tmp, ranges)
        except ClipBudgetFull as exc:
            self._consume_pending(kills, generation, len(events))
            self._finish_highlight_notice(notice, "skipped", str(exc))
            return
        except Exception as e:
            log(f"Replay save failed: {e}")
            clip_path = None
        if clip_path is None:
            self.health.add(save_errors=1)
            status = self.recorder.status()
            starting = status.get("state") == "starting"
            self._finish_highlight_notice(notice, "warming_up" if starting else "failed",
                                          "The replay buffer is warming up. RoundLatch will retry."
                                          if starting else "The recorder could not save the highlight. RoundLatch will retry while it is in the buffer.")
            with self._lock:
                if generation == self._match_generation and token is self._timer_token:
                    # A fresh kill supersedes this retry and starts a new debounce.
                    self._arm_timer(max(0.0, min(2.0, expires_at - time.monotonic())))
                    log("Recorder produced no clip. Retrying while the streak is in the buffer.")
            return

        self._consume_pending(kills, generation, len(events))
        match["kill_markers"] = playback_markers(retained, spans)
        return notice, clip_path == raw_tmp, (clip_path, recent_kills, map_name, round_n, side, steam_name, steam_id, match)

    def _replay_window(self) -> float:
        requested = float(self.cfg.get("recording.clip_seconds", 30))
        debounce = float(self.cfg.get("engine.debounce_sec"))
        segment = max(1, int(self.cfg.get("recording.segment_time", 2)))
        history = HIGHLIGHT_HISTORY if self.cfg.get("recording.backend") == "builtin" else 0
        return max(requested, history, max(debounce, self.cfg.highlight_padding()[1]) + 2 * segment)

    def _publish_clip(self, clip_path: Path, kills: int, map_name: str, round_n: int,
                      side: str, steam_name: str, steam_id: str, metadata: dict, *, generated=False) -> None:
        # Produce a share-ready version (intro card + fades); fall back to raw.
        produced = clip_path
        try:
            polished = None
            prioritize_fps = self.cfg.get("recording.backend") == "builtin" and self.cfg.game_fps_priority()
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
        try:
            clip = self._catalog_clip(final, kills, map_name, round_n, side, metadata=metadata)
        except ClipBudgetFull:
            if generated:
                final.unlink(missing_ok=True)
            raise
        caption = format_caption(kills, map_name, round_n, side)
        try:
            self.fan_out(clip, caption, automatic=True)
        except Exception as exc:
            log(f"Could not share the saved highlight: {exc}")

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
            log(f"Could not finalize clip {src.name}: {e}")
            return src

    def _consume_pending(self, kills: int, generation: int, event_count: int) -> None:
        with self._lock:
            if generation == self._match_generation:
                del self._kill_events[:event_count]
                self._state["pending_kills"] = max(0, self._state["pending_kills"] - kills)

    def _check_clip_budget(self) -> None:
        budget = self.cfg.clip_budget_bytes()
        if budget and self.catalog.used_bytes() >= budget:
            raise ClipBudgetFull()

    def _catalog_clip(self, path: Path, kills, map_name, round_n, side, *, title=None, tags=None,
                      metadata=None) -> Clip:
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
            title=title if title is not None else format_caption(kills, map_name, round_n, side),
            tags=tags if tags is not None else [],
            size_mb=round(path.stat().st_size / (1024 * 1024), 1),
            duration=round(media.probe_duration(ffmpeg, path), 1) if ffmpeg else 0.0,
            thumb=thumb.name if thumb else "",
            **(metadata or {}),
        )
        try:
            self.catalog.add(clip, budget=self.cfg.clip_budget_bytes())
        except OSError:
            if thumb is not None:
                thumb.unlink(missing_ok=True)
            raise
        log(f"Cataloged clip {cid} ({clip.size_mb} MB)")
        return clip

    def trim_clip(self, original: Clip, start: float, end: float) -> Clip | None:
        self._check_clip_budget()
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            raise ValueError("FFmpeg is unavailable.")
        source = Path(original.path)
        duration = media.probe_duration(ffmpeg, source)
        if duration <= 0:
            raise ValueError("Could not read the clip duration.")
        # Browser and container duration can differ by an audio packet.
        if end > duration + 0.1 or min(end, duration) - start < 0.249:
            raise ValueError("Choose at least 0.25 seconds within the clip.")
        folder = self.clips_dir()
        destination = folder / f"trim_{uuid.uuid4().hex}.mp4"
        with tempfile.TemporaryDirectory(prefix=".aegis-trim-", dir=folder) as scratch:
            staged = Path(scratch) / "clip.mp4"
            if not media.trim_clip(ffmpeg, source, staged, start, min(end, duration)):
                return None
            staged.replace(destination)
        try:
            title = (original.title.strip() or "Clip")[:230] + " (trim)"
            tags = list(dict.fromkeys([*original.tags, "trimmed"]))
            markers = [dict(marker, time=round(marker["time"] - start, 3))
                       for marker in original.kill_markers if start <= marker["time"] < min(end, duration)]
            metadata = {"match_id": original.match_id, "match_mode": original.match_mode,
                        "match_started": original.match_started, "kill_markers": markers}
            round_n = markers[-1]["round"] if markers else original.round_n if original.match_id else 0
            return self._catalog_clip(destination, sum(m["kills"] for m in markers), original.map_name,
                                      round_n, original.side, title=title, tags=tags, metadata=metadata)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def fan_out(self, clip: Clip, caption: str, *, automatic: bool = False) -> dict[str, str]:
        """Send a clip to every enabled uploader; record per-target status."""
        path = Path(clip.path)
        results: dict[str, str] = {}
        for up in uploaders.build_enabled(self.cfg):
            if up.name == "gallery":
                self.catalog.set_upload_status(clip.id, "gallery", "ok")
                results["gallery"] = "ok"
                continue
            if automatic and not self.cfg.get("uploads.automatic", True):
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
        self._check_clip_budget()
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

        clip = self._catalog_test_clip(out, "Test clip (ACE preview)", 5, "de_dust2")
        return {"ok": True, "clip_id": clip.id}

    def _catalog_test_clip(self, path: Path, title: str, kills: int, map_name: str) -> Clip:
        try:
            return self._catalog_clip(path, kills, map_name, 0, "?", title=title, tags=["test"])
        except ClipBudgetFull:
            path.unlink(missing_ok=True)
            raise

    def save_replay(self) -> dict:
        with self._lock:
            match = self._match.copy()
            match_observed_at = self._match_observed_at
            last_gsi = self._last_gsi
            events = self._recent_kills[:]
            map_name = self._state["map_name"]
            round_n = self._state["round_n"]
            side = self._state["side"]
        try:
            self._check_clip_budget()
            out = self.clips_dir() / f"replay_{uuid.uuid4().hex[:10]}.mp4"
            captured, spans = self._record_replay(float(self.cfg.get("recording.clip_seconds", 30)), out)
        except ClipBudgetFull as exc:
            return {"ok": False, "detail": str(exc)}
        except OSError as exc:
            self.health.add(save_errors=1)
            log(f"Replay could not be written: {exc}")
            detail = "The save drive is full." if paths.disk_full(exc) else "The clip folder is unavailable or unwritable."
            return {"ok": False, "detail": detail}
        except ValueError:
            self.health.add(save_errors=1)
            return {"ok": False, "detail": "The clip folder path is invalid."}
        if not captured:
            self.health.add(save_errors=1)
            status = self.recorder.status()
            detail = status.get("save_error") or {
                "starting": "The replay buffer is still warming up.",
                "waiting_game": "Open CS2 and wait for the replay buffer.",
                "error": "Recording stopped. Open Activity for details.",
            }.get(status.get("state"), "The replay buffer is unavailable. Check capture status and Activity.")
            return {"ok": False, "detail": detail}
        warning = ""
        generated = captured == out
        if self.cfg.get("storage.clips_dir") and captured.parent != out.parent:
            destination = out.with_suffix(captured.suffix)
            try:
                shutil.move(str(captured), str(destination))
                captured = destination
            except OSError as exc:
                log(f"Could not move the OBS replay to the clip folder: {exc}")
                try:
                    destination.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    log(f"Could not remove the partial replay copy: {cleanup_error}")
                problem = "The save drive was full." if paths.disk_full(exc) else "The clip folder was unavailable."
                warning = f"{problem} OBS kept the file in its replay folder."
        try:
            markers = playback_markers(events, spans)
            if not match or not any(end >= match_observed_at and start <= last_gsi + 25 for start, end in spans):
                match, map_name, round_n, side = {}, "Manual replay", 0, "?"
            match["kill_markers"] = markers
            clip = self._catalog_clip(captured, sum(m["kills"] for m in markers), map_name,
                                      markers[-1]["round"] if markers else round_n, side,
                                      title="Manual replay", metadata=match)
        except ClipBudgetFull as exc:
            if generated:
                captured.unlink(missing_ok=True)
            return {"ok": False, "detail": str(exc)}
        except OSError as exc:
            self.health.add(save_errors=1)
            log(f"Replay file saved, but could not write the library: {exc}")
            detail = "The replay file was saved, but the library could not be updated."
            return {"ok": False, "detail": detail}
        self.health.add(clips_saved=1)
        return {"ok": True, "clip_id": clip.id, "warning": warning}

    def save_shortcut_replay(self) -> None:
        try:
            result = self.save_replay()
        except Exception as exc:
            self.health.add(save_errors=1)
            log(f"Replay shortcut failed: {exc}")
            result = {"ok": False, "detail": "Could not save the replay. Check Activity."}
        text = (result.get("warning") or "Replay saved to your library.") if result["ok"] else result["detail"]
        self.replay_receipt = {"id": uuid.uuid4().hex, "ok": result["ok"], "message": text,
                               "clip_id": result.get("clip_id")}
        log(f"Replay shortcut: {text}")
        notify = self.notify_replay
        if notify is not None:
            try:
                notify(text)
            except Exception as exc:
                log(f"Could not show the replay notification: {exc}")

    def trigger_capture_test(self, seconds: int = 5) -> dict:
        """Record a few seconds of the REAL screen — proves ddagrab capture + the
        GPU encoder work on this machine, which the synthetic test can't."""
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return {"ok": False, "detail": "ffmpeg not found"}
        self._check_clip_budget()
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
        clip = self._catalog_test_clip(out, f"Screen capture test ({method})", 0, "screen capture test")
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
