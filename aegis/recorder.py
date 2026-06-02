"""Recording backends — turn "save the last N seconds" into a clip file.

Two implementations behind one interface so the engine doesn't care which is used:

  BuiltinRecorder  (default, no OBS needed)
    Runs ffmpeg continuously capturing the screen into a *rolling buffer* of small
    segment files (like a DVR). On a kill, the most recent segments are stream-
    copied into one clip — cheap, no re-encode at save time. Capture uses the
    Desktop Duplication API (ddagrab), which sees fullscreen games where GDI
    can't, and a hardware encoder (NVENC/AMF/QSV) when present, falling back to a
    low-CPU x264 path for weak machines. To stay light it can record only while
    the game is actually running.

  ObsRecorder  (optional "pro" backend)
    The original path: ask OBS to flush its replay buffer and find the new file.

Design notes:
  - The ffmpeg command builder and segment-selection math are pure functions
    (build_capture_cmd / pick_segments / pick_encoder) so they're unit-testable
    without a screen or a GPU.
  - Nothing here raises into the engine; failures log and return None/False.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import sys
import threading
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from . import media, paths
from .config import Config
from .log import log

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Quality presets -> (width, height, fps, video bitrate). "source" keeps native size.
PRESETS: dict[str, tuple] = {
    "low":    (1280, 720, 30, "6M"),    # low-end friendly
    "medium": (1600, 900, 30, "10M"),
    "high":   (1920, 1080, 60, "16M"),
    "source": (0, 0, 60, "16M"),
}

# Encoder preference order; first one ffmpeg reports as available wins.
_HW_ENCODERS = ["h264_nvenc", "h264_amf", "h264_qsv"]


# ───────── pure helpers (unit-testable) ─────────
def pick_encoder(encoders_text: str, preference: str = "auto") -> str:
    """Choose an h264 encoder from `ffmpeg -encoders` output.

    preference: "auto" picks the best available hardware encoder, else libx264.
    An explicit name (e.g. "nvenc") is honored if present.
    """
    avail = encoders_text or ""
    if preference and preference not in ("auto", "x264"):
        name = preference if preference.startswith("h264_") else f"h264_{preference}"
        if name in avail:
            return name
    if preference != "x264":
        for enc in _HW_ENCODERS:
            if enc in avail:
                return enc
    return "libx264"


def _encoder_args(encoder: str, bitrate: str) -> list[str]:
    if encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-b:v", bitrate]
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", bitrate]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "speed", "-b:v", bitrate]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "veryfast", "-b:v", bitrate]
    return ["-c:v", encoder, "-b:v", bitrate]


def build_capture_cmd(
    ffmpeg: str,
    buffer_dir: Path,
    *,
    width: int,
    height: int,
    fps: int,
    encoder: str,
    bitrate: str,
    segment_time: int,
    segment_wrap: int,
    use_ddagrab: bool = True,
) -> list[str]:
    """ffmpeg command for the continuous rolling-buffer capture.

    Writes seg_%03d.ts into buffer_dir, cycling over segment_wrap files so only
    ~segment_time*segment_wrap seconds are ever kept on disk.
    """
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]

    # Desktop Duplication (sees fullscreen games) -> system memory in nv12.
    chain = "ddagrab=output_idx=0:framerate={fps},hwdownload,format=bgra".format(fps=fps)
    if width and height:
        chain += f",scale={width}:{height}"
    chain += ",format=nv12"

    if use_ddagrab:
        cmd += ["-filter_complex", chain]
    else:
        # Fallback screen grab (GDI) — works without ddagrab but not on some
        # exclusive-fullscreen games.
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]
        if width and height:
            cmd += ["-vf", f"scale={width}:{height}"]

    cmd += _encoder_args(encoder, bitrate)
    cmd += [
        "-f", "segment",
        "-segment_time", str(segment_time),
        "-segment_wrap", str(segment_wrap),
        "-reset_timestamps", "1",
        "-segment_format", "mpegts",
        str(buffer_dir / "seg_%03d.ts"),
    ]
    return cmd


def pick_segments(entries: list[tuple[Path, float]], clip_seconds: float,
                  segment_time: float) -> list[Path]:
    """Pick the newest segments covering `clip_seconds`, in chronological order.

    entries: (path, mtime) pairs. We drop the single newest file because it's the
    one ffmpeg is still writing, then take enough older ones to span the window.
    """
    if not entries:
        return []
    ordered = sorted(entries, key=lambda e: e[1])  # oldest -> newest
    complete = ordered[:-1] if len(ordered) > 1 else ordered
    need = max(1, math.ceil(clip_seconds / max(segment_time, 0.1)) + 1)
    chosen = complete[-need:]
    return [p for p, _ in chosen]


# ───────── interface ─────────
class Recorder(ABC):
    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
    @abstractmethod
    def save(self, seconds: float, out_path: Path) -> Path | None: ...
    @abstractmethod
    def status(self) -> dict: ...


def make_recorder(cfg: Config) -> Recorder:
    backend = cfg.get("recording.backend", "builtin")
    if backend == "obs":
        return ObsRecorder(cfg)
    return BuiltinRecorder(cfg)


# ───────── built-in ffmpeg recorder ─────────
class BuiltinRecorder(Recorder):
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._supervisor: threading.Thread | None = None
        self._stop = threading.Event()
        self._encoder = "?"
        # Each recorder instance gets its OWN buffer dir. If a config change spins
        # up a new recorder, its ffmpeg can't collide with a lingering old one's
        # segment files, and an in-flight save() reads from a stable directory.
        self._bdir = paths.buffer_dir() / f"rec_{uuid.uuid4().hex[:8]}"
        self._bdir.mkdir(parents=True, exist_ok=True)

    # -- lifecycle --
    def start(self) -> None:
        if self._supervisor and self._supervisor.is_alive():
            return
        self._stop.clear()
        self._supervisor = threading.Thread(target=self._run, daemon=True)
        self._supervisor.start()

    def stop(self) -> None:
        """Synchronous stop: signal, kill ffmpeg, and WAIT for the supervisor to
        exit. Without the join, restart_recording() could create a new recorder
        whose ffmpeg writes to the same buffer dir as this one's lingering
        process — corrupting both. Joining guarantees no overlap."""
        self._stop.set()
        self._kill_proc()
        sup = self._supervisor
        if sup and sup.is_alive() and sup is not threading.current_thread():
            sup.join(timeout=6.0)
        # ffmpeg is now stopped; drop this instance's buffer dir (best effort).
        try:
            shutil.rmtree(self._bdir, ignore_errors=True)
        except Exception:
            pass

    def _run(self) -> None:
        """Supervisor: keep ffmpeg capturing while enabled (and, if gated, while
        the game is running); restart it if it dies. Never lets an exception kill
        the thread silently."""
        gate = bool(self.cfg.get("recording.only_when_game_running", True))
        game = self.cfg.get("recording.game_process", "cs2.exe")
        while not self._stop.is_set():
            try:
                want = (not gate) or _process_running(game)
                with self._lock:
                    running = self._proc is not None and self._proc.poll() is None
                if want and not running:
                    self._spawn()
                elif not want and running:
                    self._kill_proc()
            except Exception as e:
                log(f"Built-in recorder supervisor error: {e}")
            self._stop.wait(3.0)
        self._kill_proc()  # ensure ffmpeg is gone when the loop exits

    def _spawn(self) -> None:
        if self._stop.is_set():        # bail if a stop raced in
            return
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            log("Built-in recorder: ffmpeg not found — cannot capture")
            self._stop.wait(10.0)
            return

        bdir = self._bdir
        for old in bdir.glob("seg_*.ts"):
            try:
                old.unlink()
            except Exception:
                pass

        preset = self.cfg.get("recording.preset", "medium")
        w, h, fps, bitrate = PRESETS.get(preset, PRESETS["medium"])
        fps = int(self.cfg.get("recording.fps", fps) or fps)
        self._encoder = pick_encoder(_encoders_text(ffmpeg),
                                     self.cfg.get("recording.encoder", "auto"))
        seg_time = int(self.cfg.get("recording.segment_time", 2))
        buffer_secs = int(self.cfg.get("recording.buffer_seconds", 45))
        wrap = max(4, math.ceil(buffer_secs / seg_time) + 2)
        use_dda = self.cfg.get("recording.capture", "ddagrab") != "gdigrab"

        cmd = build_capture_cmd(
            ffmpeg, bdir, width=w, height=h, fps=fps, encoder=self._encoder,
            bitrate=bitrate, segment_time=seg_time, segment_wrap=wrap, use_ddagrab=use_dda,
        )
        log(f"Built-in recorder starting ({preset}, {self._encoder}, {fps}fps)")
        try:
            with self._lock:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=_NO_WINDOW,
                )
            # Ensure this ffmpeg dies if the app crashes / is killed / self-updates,
            # so it can't keep recording or lock the bundled ffmpeg.exe.
            from . import winjob
            winjob.guard(self._proc)
        except Exception as e:
            log(f"Built-in recorder failed to start: {e}")
            self._proc = None
            self._stop.wait(10.0)

    def _kill_proc(self) -> None:
        with self._lock:
            p = self._proc
            self._proc = None
        if p and p.poll() is None:
            try:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
            except Exception:
                pass

    # -- save --
    def save(self, seconds: float, out_path: Path) -> Path | None:
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return None
        with self._lock:                       # snapshot to avoid a torn read mid-restart
            proc = self._proc
        if proc is None or proc.poll() is not None:
            log("Built-in recorder isn't capturing (game not running?) — no clip")
            return None

        seg_time = int(self.cfg.get("recording.segment_time", 2))
        bdir = self._bdir
        # Let the in-progress segment flush so the kill moment is on disk.
        time.sleep(min(seg_time, 2))
        entries = [(p, p.stat().st_mtime) for p in bdir.glob("seg_*.ts") if p.stat().st_size > 0]
        segs = pick_segments(entries, seconds, seg_time)
        if not segs:
            log("Built-in recorder: no buffer segments to assemble")
            return None

        listfile = bdir / "concat.txt"
        listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-f", "concat", "-safe", "0", "-i", str(listfile),
               "-c", "copy", "-movflags", "+faststart", str(out_path)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, creationflags=_NO_WINDOW)
        except Exception as e:
            log(f"Built-in recorder concat failed: {e}")
            return None
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return out_path
        log(f"Built-in recorder save failed: {(r.stderr or '')[-200:]}")
        return None

    def status(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        return {"backend": "builtin", "capturing": running, "encoder": self._encoder}


# ───────── OBS backend (optional) ─────────
class ObsRecorder(Recorder):
    def __init__(self, cfg: Config):
        from .obs_client import ObsClient
        self.cfg = cfg
        self.obs = ObsClient(cfg.get("obs.host"), int(cfg.get("obs.port")),
                             cfg.get("obs.password", ""))

    def start(self) -> None:  # OBS records itself; nothing to spin up
        self.obs.connected()

    def stop(self) -> None:
        pass

    def save(self, seconds: float, out_path: Path) -> Path | None:
        replay_dir = Path(self.cfg.get("obs.replay_dir") or (Path.home() / "Videos"))
        if not self.obs.save_replay_buffer():
            return None
        return _wait_for_new_clip(replay_dir, float(self.cfg.get("engine.clip_wait_sec", 8)))

    def status(self) -> dict:
        return {"backend": "obs", "capturing": self.obs.replay_buffer_active(),
                "encoder": "obs", "obs_connected": self.obs.connected()}


# ───────── shared utilities ─────────
def _encoders_text(ffmpeg: str) -> str:
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                          capture_output=True, text=True, creationflags=_NO_WINDOW)
        return r.stdout or ""
    except Exception:
        return ""


def _process_running(name: str) -> bool:
    """True if a process called `name` is running (Windows tasklist)."""
    if sys.platform != "win32":
        return True  # don't gate on non-Windows dev machines
    try:
        r = subprocess.run(["tasklist", "/fi", f"imagename eq {name}", "/nh"],
                          capture_output=True, text=True, creationflags=_NO_WINDOW)
        return name.lower() in (r.stdout or "").lower()
    except Exception:
        return True


def _wait_for_new_clip(replay_dir: Path, timeout: float) -> Path | None:
    """Poll an OBS output dir for a freshly written video (OBS backend)."""
    start = time.time()
    while time.time() < start + timeout:
        time.sleep(0.5)
        try:
            cands = [f for f in replay_dir.iterdir()
                     if f.is_file() and f.suffix.lower() in (".mp4", ".mkv", ".mov")
                     and f.stat().st_mtime >= start - 1]
        except FileNotFoundError:
            log(f"OBS replay dir not found: {replay_dir}")
            return None
        if cands:
            latest = max(cands, key=lambda f: f.stat().st_mtime)
            prev = -1
            for _ in range(12):
                size = latest.stat().st_size
                if size > 0 and size == prev:
                    return latest
                prev = size
                time.sleep(0.3)
            return latest
    return None
