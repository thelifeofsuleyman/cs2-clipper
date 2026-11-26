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
import tempfile
import threading
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from . import media, paths
from .audio import ProcessAudioBuffer, SpeakerBuffer
from .config import Config
from .log import log

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Quality presets -> (width, height, fps, video bitrate). "source" keeps native size.
PRESETS: dict[str, tuple] = {
    "gpu_only": (0, 0, 30, "8M"),
    "light":  (960, 540, 24, "3M"),
    "low":    (1280, 720, 30, "6M"),    # low-end friendly
    "medium": (1600, 900, 30, "10M"),
    "high":   (1920, 1080, 60, "16M"),
    "source": (0, 0, 60, "16M"),
}

# Encoder preference order; first one ffmpeg reports as available wins.
_HW_ENCODERS = ["h264_nvenc", "h264_amf", "h264_qsv"]
_D3D11_ENCODERS = {"h264_nvenc", "h264_amf"}
HIGHLIGHT_HISTORY = 120
HIGHLIGHT_LEAD = 2.0
HIGHLIGHT_TAIL = 1.0
REPLAY_GRACE_SECONDS = 30


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


def capture_candidates(ffmpeg: str, cfg: Config) -> list[tuple[str, str]]:
    encoders = _encoders_text(ffmpeg)
    preference = cfg.get("recording.encoder", "auto")
    primary = pick_encoder(encoders, preference)
    choices = [primary]
    if preference != "x264":
        choices.extend(e for e in _HW_ENCODERS if e in encoders and e != primary)
    if "libx264" not in choices:
        choices.append("libx264")
    method = cfg.get("recording.capture", "ddagrab")
    methods = ("gdigrab", "ddagrab") if method == "gdigrab" else ("ddagrab", "gdigrab")
    preset = cfg.get("recording.preset")
    if preset == "gpu_only":
        return [("ddagrab-d3d11", encoder) for encoder in choices if encoder in _D3D11_ENCODERS]
    prefer_direct = preset != "light" and (cfg.game_fps_priority() or preset == "source")
    candidates = []
    for method in methods:
        if method == "ddagrab" and prefer_direct:
            candidates.extend(("ddagrab-d3d11", e) for e in choices if e in _D3D11_ENCODERS)
        candidates.extend((method, encoder) for encoder in choices)
    return candidates


def _encoder_args(encoder: str, bitrate: str, performance: bool = False,
                  compact: bool = False) -> list[str]:
    rate = ["-b:v", bitrate]
    if compact:
        cap = ["-maxrate", bitrate, "-bufsize", bitrate]
        if encoder == "h264_nvenc":
            rate = ["-rc", "vbr", "-cq", "21", "-b:v", "0", *cap]
        elif encoder == "libx264":
            rate = ["-crf", "21", *cap]
        else:
            rate = ["-b:v", f"{int(bitrate[:-1]) * 700}k", *cap]
    if encoder == "libx264":
        args = ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                *rate]
        return [*args, "-threads", "2"] if performance else args
    if encoder == "h264_nvenc":
        if performance:
            return ["-c:v", encoder, "-preset", "p2", "-tune", "ll", "-bf", "0",
                    "-rc-lookahead", "0", *rate]
        return ["-c:v", "h264_nvenc", "-preset", "p4", *rate]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "speed", *rate]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "veryfast", *rate]
    return ["-c:v", encoder, *rate]


def capture_options(cfg: Config, encoder: str) -> tuple[int, int, int, str]:
    preset = cfg.get("recording.preset", "medium")
    if preset == "light":
        return PRESETS["light"]
    w, h, fps, bitrate = PRESETS.get(preset, PRESETS["medium"])
    fps = int(cfg.get("recording.fps", fps) or fps)
    if cfg.game_fps_priority():
        fps = min(fps, 30)
        if encoder == "libx264":
            w, h, _, bitrate = PRESETS["low"]
    return w, h, fps, bitrate


def capture_video_args(width: int, height: int, fps: int, encoder: str, bitrate: str,
                       method: str, performance: bool, compact: bool = False) -> list[str]:
    args = []
    if method == "gdigrab":
        args += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]
        if width and height:
            scale = f"scale={width}:{height}"
            if performance:
                args += ["-filter_threads", "2"]
                scale += ":flags=fast_bilinear"
            args += ["-vf", scale]
    else:
        chain = f"ddagrab=output_idx=0:framerate={fps}"
        if performance:
            chain += ":draw_mouse=0"
        if method != "ddagrab-d3d11":
            chain += ",hwdownload,format=bgra"
            if width and height:
                chain += f",scale={width}:{height}"
                if performance:
                    chain += ":flags=fast_bilinear"
            chain += ",format=nv12"
            if performance:
                args += ["-filter_complex_threads", "2"]
        args += ["-filter_complex", chain]
    return [*args, *_encoder_args(encoder, bitrate, performance, compact)]


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
    direct_gpu: bool = False,
    performance: bool = False,
    compact: bool = False,
) -> list[str]:
    """ffmpeg command for the continuous rolling-buffer capture.

    Writes seg_%03d.ts into buffer_dir, cycling over segment_wrap files so only
    ~segment_time*segment_wrap seconds are ever kept on disk.
    """
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]

    method = "ddagrab-d3d11" if direct_gpu else ("ddagrab" if use_ddagrab else "gdigrab")
    cmd += capture_video_args(width, height, fps, encoder, bitrate, method, performance, compact)
    cmd += [
        "-g", str(fps * segment_time),
        "-force_key_frames", f"expr:gte(t,n_forced*{segment_time})",
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


def highlight_ranges(kills: list[float], before: float = HIGHLIGHT_LEAD,
                     after: float = HIGHLIGHT_TAIL) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for kill in kills:
        start, end = kill - before, kill + after
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], end)
        else:
            ranges.append((start, end))
    return ranges


def highlight_segments(entries: list[tuple[Path, float]], ranges: list[tuple[float, float]],
                       segment_time: float, after: float = HIGHLIGHT_TAIL) -> list[Path]:
    complete = sorted(entries, key=lambda entry: entry[1])[:-1]
    if not complete or not ranges or complete[-1][1] < ranges[-1][1] - 0.25:
        return []
    last_kill = ranges[-1][1] - after
    if last_kill < complete[0][1] - segment_time:
        return []
    # Segment timestamps come from file writes. Ignore a tiny boundary overlap
    # so timestamp jitter does not append a whole extra segment to each cut.
    tolerance = 0.15
    return [segment for segment, end in complete
            if any(start + tolerance < end and stop - tolerance > end - segment_time
                   for start, stop in ranges)]


# ───────── interface ─────────
class Recorder(ABC):
    last_saved_spans: tuple[tuple[float, float], ...] = ()

    @abstractmethod
    def start(self) -> None: ...
    @abstractmethod
    def stop(self) -> None: ...
    @abstractmethod
    def save(self, seconds: float, out_path: Path,
             ranges: list[tuple[float, float]] | None = None) -> Path | None: ...
    @abstractmethod
    def status(self) -> dict: ...


def make_recorder(cfg: Config, health=None) -> Recorder:
    backend = cfg.get("recording.backend", "builtin")
    if backend == "obs":
        return ObsRecorder(cfg)
    return BuiltinRecorder(cfg, health)


# ───────── built-in ffmpeg recorder ─────────
class BuiltinRecorder(Recorder):
    def __init__(self, cfg: Config, health=None):
        self.cfg = cfg
        self._health = health
        self._capture_started = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._snapshot_lock = threading.Lock()
        self._buffer_generation = 0
        self._retained_until = 0.0
        self._retained_speaker: SpeakerBuffer | ProcessAudioBuffer | None = None
        self._supervisor: threading.Thread | None = None
        self._stop = threading.Event()
        self._encoder = "?"
        self._fps = 0
        self._method = ""
        self._stage = "idle"
        self._detail = ""
        self._save_error = ""
        self._stderr = None
        self._last_segment_at = 0.0
        self._last_segment_write = 0
        self._speaker: SpeakerBuffer | ProcessAudioBuffer | None = None
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
        self._bdir.mkdir(parents=True, exist_ok=True)
        self._supervisor = threading.Thread(target=self._run, daemon=True)
        self._supervisor.start()

    def stop(self) -> None:
        """Synchronous stop: signal, kill ffmpeg, and WAIT for the supervisor to
        exit. Without the join, restart_recording() could create a new recorder
        whose ffmpeg writes to the same buffer dir as this one's lingering
        process — corrupting both. Joining guarantees no overlap."""
        self._stop.set()
        with self._lock:
            self._retained_until = 0.0
            self._retained_speaker = None
        self._kill_proc()
        sup = self._supervisor
        if sup and sup.is_alive() and sup is not threading.current_thread():
            sup.join(timeout=6.0)
        if sup is None or not sup.is_alive():
            shutil.rmtree(self._bdir, ignore_errors=True)

    def _run(self) -> None:
        """Supervisor: keep ffmpeg capturing while enabled (and, if gated, while
        the game is running); restart it if it dies. Never lets an exception kill
        the thread silently."""
        gate = bool(self.cfg.get("recording.only_when_game_running", True))
        game = self.cfg.get("recording.game_process", "cs2.exe")
        game_audio = self.cfg.audio_source() == "cs2"
        segment_time = max(1, int(self.cfg.get("recording.segment_time", 2)))
        choices: list[tuple[str, str]] = []
        next_choice = 0
        while not self._stop.is_set():
            try:
                pid = None
                try:
                    if game_audio and sys.platform == "win32":
                        from .winprocess import process_id
                        try:
                            pid = process_id("cs2.exe")
                        except OSError:
                            if gate and game.casefold() == "cs2.exe":
                                raise
                    want = (not gate) or (
                        pid is not None if game_audio and game.casefold() == "cs2.exe"
                        else _process_running(game)
                    )
                except OSError as e:
                    if self._stage != "error":
                        log(f"Stopped capture because CS2 could not be detected: {e}")
                    self._kill_proc()
                    choices, next_choice = [], 0
                    self._stage = "error"
                    self._detail = "Windows could not check whether CS2 is running. Retrying."
                    self._stop.wait(2.0)
                    continue
                with self._lock:
                    proc = self._proc
                if not want:
                    self._game_closed()
                    choices = []
                    next_choice = 0
                else:
                    if proc is not None:
                        if proc.poll() is not None:
                            self._capture_failed(f"FFmpeg exited ({proc.returncode})")
                        elif (problem := self._check_segment_progress(segment_time)):
                            self._capture_failed(problem)
                    if self._proc is None:
                        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
                        if not ffmpeg:
                            self._stage = "error"
                            self._detail = "FFmpeg not found. Use the Windows installer or set ffmpeg_path."
                            self._stop.wait(8)
                            continue
                        if not choices:
                            choices = capture_candidates(ffmpeg, self.cfg)
                            if not choices:
                                self._stage = "error"
                                self._detail = "Direct GPU capture needs an available NVENC or AMF encoder. Choose another quality preset to allow fallback."
                                self._stop.wait(12)
                                continue
                        if next_choice >= len(choices):
                            next_choice = 0
                            self._stage = "error"
                            self._stop.wait(12)
                            continue
                        method, encoder = choices[next_choice]
                        next_choice += 1
                        self._spawn(ffmpeg, method, encoder, segment_time)
                    if game_audio:
                        with self._lock:
                            speaker = self._speaker
                        if isinstance(speaker, ProcessAudioBuffer):
                            speaker.refresh(pid)
            except Exception as e:
                self._stage = "error"
                self._detail = str(e)
                log(f"Built-in recorder supervisor error: {e}")
                self._kill_proc()
            self._stop.wait(2.0)
        self._kill_proc()  # ensure ffmpeg is gone when the loop exits
        shutil.rmtree(self._bdir, ignore_errors=True)
        self._stage = "idle"

    def _game_closed(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self._proc is not None and self._stage == "ready":
                self._retained_until = now + REPLAY_GRACE_SECONDS
                self._retained_speaker = self._speaker
            expired = 0 < self._retained_until <= now
        self._kill_proc()
        if expired:
            self._discard_segments()
        self._stage = "waiting_game"
        self._detail = ""

    def _check_segment_progress(self, segment_time: int) -> str:
        files = self._segment_entries()
        writes = sorted(mtime for _, mtime in files)
        newest_write = writes[-2] if len(writes) > 1 else 0
        now = time.monotonic()
        if newest_write != self._last_segment_write:
            self._last_segment_write = newest_write
            self._last_segment_at = now
        if now - self._last_segment_at > max(10, segment_time * 3):
            return "FFmpeg stopped writing replay segments"
        if self._stage == "starting" and len(files) > 1:
            self._stage = "ready"
            self._detail = ""
            if self._capture_started is not None:
                self._health.add(capture_ready=1, capture_start_ms=round((now - self._capture_started) * 1000))
                self._capture_started = None
            log(f"Replay buffer ready ({self._method}, {self._encoder})")
        return ""

    def _segment_entries(self) -> list[tuple[Path, int]]:
        entries = []
        for segment in self._bdir.glob("seg_*.ts"):
            try:
                stat = segment.stat()
                if stat.st_size:
                    entries.append((segment, stat.st_mtime_ns))
            except FileNotFoundError:
                continue
        return entries

    def _spawn(self, ffmpeg: str, method: str, encoder: str, seg_time: int) -> None:
        if self._stop.is_set():        # bail if a stop raced in
            return

        bdir = self._bdir
        self._discard_segments()

        w, h, fps, bitrate = capture_options(self.cfg, encoder)
        performance = self.cfg.game_fps_priority()
        buffer_secs = max(int(self.cfg.get("recording.buffer_seconds", 45)),
                          HIGHLIGHT_HISTORY,
                          math.ceil(float(self.cfg.get("recording.clip_seconds", 30))),
                          math.ceil(float(self.cfg.get("engine.debounce_sec", 7))) + 2 * seg_time)
        wrap = max(4, math.ceil(buffer_secs / seg_time) + 2)

        cmd = build_capture_cmd(
            ffmpeg, bdir, width=w, height=h, fps=fps, encoder=encoder,
            bitrate=bitrate, segment_time=seg_time, segment_wrap=wrap,
            use_ddagrab=method != "gdigrab", direct_gpu=method == "ddagrab-d3d11",
            performance=performance,
            compact=bool(self.cfg.get("recording.compact_video")),
        )
        self._method, self._encoder = method, encoder
        self._fps = fps
        self._stage = "starting"
        self._last_segment_write = 0
        track = self._health is not None and self._health.enabled
        self._capture_started = time.monotonic() if track else None
        if self._capture_started is not None:
            self._health.add(capture_attempts=1)
        if track:
            cmd[1:1] = ["-nostats", "-progress", "pipe:1", "-stats_period", "2"]
        log(f"Built-in recorder starting ({method}, {encoder}, {fps}fps)")
        stderr = None
        try:
            stderr = tempfile.TemporaryFile()
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE if track else subprocess.DEVNULL,
                stderr=stderr, creationflags=_NO_WINDOW,
            )
        except (OSError, ValueError) as e:
            if stderr:
                stderr.close()
            self._capture_failed(str(e))
            return

        if track:
            threading.Thread(target=self._track_progress, args=(proc.stdout,), daemon=True).start()

        from . import winjob
        winjob.guard(proc)
        speaker = None
        if not self._stop.is_set():
            source = self.cfg.audio_source()
            if source == "desktop":
                candidate = SpeakerBuffer(buffer_secs + 2 * seg_time)
                if candidate.start():
                    speaker = candidate
            elif source == "cs2":
                speaker = ProcessAudioBuffer(buffer_secs + 2 * seg_time)
        with self._lock:
            stopped = self._stop.is_set()
            if not stopped:
                self._last_segment_at = time.monotonic()
                self._stderr = stderr
                self._proc = proc
                self._speaker = speaker
        if stopped:
            self._terminate(proc)
            stderr.close()
            if speaker:
                speaker.stop()

    def _track_progress(self, stream) -> None:
        counters = {}
        previous = (0, 0) if self._health.enabled else None
        with stream:
            for line in stream:
                key, _, raw = line.strip().partition(b"=")
                if key in (b"frame", b"drop_frames"):
                    try:
                        counters[key] = int(raw)
                    except ValueError:
                        continue
                elif key == b"progress":
                    if self._health.enabled:
                        if all(key in counters for key in (b"frame", b"drop_frames")):
                            current = counters[b"frame"], counters[b"drop_frames"]
                            if previous is not None:
                                self._health.add(frames_output=current[0] - previous[0],
                                                 frames_dropped=current[1] - previous[1])
                            previous = current
                    else:
                        previous = None
                    counters.clear()
        self._health.flush()

    def _capture_failed(self, reason: str) -> None:
        if self._health is not None:
            self._health.add(capture_errors=1)
        with self._lock:
            err = self._stderr
            if err:
                err.seek(max(0, err.seek(0, 2) - 1500))
                lines = err.read().decode(errors="replace").strip().splitlines()
                if lines:
                    reason = " | ".join(lines[-3:])[:350]
        self._detail = reason
        log(f"Capture failed ({self._method}, {self._encoder}): {reason}")
        self._kill_proc()

    def _kill_proc(self) -> None:
        with self._lock:
            p = self._proc
            self._proc = None
            err, self._stderr = self._stderr, None
            speaker, self._speaker = self._speaker, None
        if speaker:
            speaker.stop()
        if p:
            self._terminate(p)
        if err:
            err.close()

    def _discard_segments(self) -> None:
        # A restarting encoder must wait until the current save has copied its files.
        with self._snapshot_lock:
            with self._lock:
                self._buffer_generation += 1
                self._retained_until = 0.0
                self._retained_speaker = None
            for segment in self._bdir.glob("seg_*.ts"):
                segment.unlink(missing_ok=True)

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
            except Exception:
                pass

    # -- save --
    def save(self, seconds: float, out_path: Path,
             ranges: list[tuple[float, float]] | None = None) -> Path | None:
        self._save_error = ""
        self.last_saved_spans = ()
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            self._save_error = "FFmpeg is unavailable."
            return None
        with self._lock:
            proc = self._proc
            generation = self._buffer_generation
            retained = time.monotonic() < self._retained_until
        live = proc is not None and proc.poll() is None
        if self._stop.is_set() or not (live or retained):
            log("Built-in recorder has no replay buffer to save")
            return None

        seg_time = max(1, int(self.cfg.get("recording.segment_time", 2)))
        bdir = self._bdir
        # Debounce has already allowed post-roll. Wait for the current segment
        # only while the buffer is warming up.
        if live and len(list(bdir.glob("seg_*.ts"))) < 2:
            self._stop.wait(min(seg_time, 2))
        offset = time.time() - time.monotonic()
        if live and ranges is None and self._stage == "ready":
            requested_at = time.monotonic()
            # Finish the segment containing the shortcut press before copying it.
            deadline = requested_at + seg_time + 0.35
            while time.monotonic() < deadline:
                writes = sorted(ns / 1e9 - offset for _, ns in self._segment_entries())
                if len(writes) > 1 and writes[-2] >= requested_at - 0.15:
                    break
                if self._stop.wait(0.1):
                    return None
                if proc.poll() is not None:
                    break

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="save_", dir=bdir) as snapshot:
                temp = Path(snapshot)
                names = []
                with self._snapshot_lock:
                    with self._lock:
                        if self._stop.is_set() or generation != self._buffer_generation:
                            return None
                        current = self._proc
                        live = current is not None and current.poll() is None
                        retained = time.monotonic() < self._retained_until
                        if not (live or retained):
                            return None
                        speaker = self._speaker if live else self._retained_speaker
                    entries = [(path, ns / 1e9 - offset) for path, ns in self._segment_entries()]
                    if len(entries) < 2:
                        self._save_error = "The replay buffer is still warming up."
                        return None
                    segs = (pick_segments(entries, seconds, seg_time) if ranges is None
                            else highlight_segments(entries, ranges, seg_time, self.cfg.highlight_padding()[1]))
                    if not segs:
                        return None
                    for i, segment in enumerate(segs):
                        name = f"clip_{i:03d}.ts"
                        shutil.copyfile(segment, temp / name)
                        names.append(name)
                listfile = temp / "concat.txt"
                listfile.write_text("".join(f"file '{name}'\n" for name in names), encoding="utf-8")
                cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                       "-f", "concat", "-safe", "1", "-i", str(listfile)]
                output = ["-movflags", "+faststart", str(out_path)]
                ends = dict(entries)
                spans = [(ends[segment] - seg_time, ends[segment]) for segment in segs]
                if speaker and (not isinstance(speaker, ProcessAudioBuffer) or speaker.buffered.is_set()):
                    try:
                        wav = temp / "speaker.wav"
                        speaker.write(spans, wav)
                        r = media.mux_speaker_audio(cmd, wav, output)
                        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
                            self.last_saved_spans = tuple(spans)
                            return out_path
                        log(f"Speaker audio mux failed: {r.stderr[-200:]}")
                    except (OSError, ValueError, subprocess.SubprocessError) as exc:
                        log(f"Could not include speaker audio: {exc}")
                r = media._run([*cmd, "-c", "copy", *output], timeout=20)
        except Exception as e:
            log(f"Built-in recorder concat failed: {e}")
            if isinstance(e, OSError):
                self._save_error = ("The save drive or replay buffer drive is full." if paths.disk_full(e)
                                    else "RoundLatch could not read the buffer or write to the clip folder.")
            out_path.unlink(missing_ok=True)
            return None
        if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            self.last_saved_spans = tuple(spans)
            return out_path
        log(f"Built-in recorder save failed: {(r.stderr or '')[-200:]}")
        if "no space left" in (r.stderr or "").lower() or "disk full" in (r.stderr or "").lower():
            self._save_error = "The save drive is full."
        out_path.unlink(missing_ok=True)
        return None

    def status(self) -> dict:
        with self._lock:
            proc = self._proc
            speaker = self._speaker
            retained = max(0, math.ceil(self._retained_until - time.monotonic()))
        ready = self._stage == "ready" and proc is not None and proc.poll() is None
        source = self.cfg.audio_source()
        audio, audio_detail = "off", ""
        if source == "desktop":
            audio = "capturing" if speaker else "unavailable" if ready else "waiting"
        elif source == "cs2":
            audio = "waiting"
            if isinstance(speaker, ProcessAudioBuffer):
                audio = "capturing" if speaker.ready.is_set() else "unavailable" if ready else "waiting"
                audio_detail = speaker.detail
        return {"backend": "builtin", "capturing": ready, "encoder": self._encoder, "fps": self._fps,
                "cpu_encoding": ready and self._encoder == "libx264",
                "method": self._method, "state": self._stage, "detail": self._detail, "audio": audio,
                "audio_source": source, "audio_detail": audio_detail,
                "replay_available": ready or bool(retained), "replay_expires_in": retained,
                "save_error": self._save_error}


# ───────── OBS backend (optional) ─────────
class ObsRecorder(Recorder):
    def __init__(self, cfg: Config):
        from .obs_client import ObsClient
        self.cfg = cfg
        self._save_error = ""
        self.obs = ObsClient(cfg.get("obs.host"), int(cfg.get("obs.port")),
                             cfg.get("obs.password", ""))

    def start(self) -> None:  # OBS records itself; nothing to spin up
        self.obs.connected()

    def stop(self) -> None:
        pass

    def save(self, seconds: float, out_path: Path,
             ranges: list[tuple[float, float]] | None = None) -> Path | None:
        self.last_saved_spans = ()
        self._save_error = ""
        replay_dir = Path(self.cfg.get("obs.replay_dir") or (Path.home() / "Videos"))
        replay_end = time.monotonic()
        requested_at = time.time()
        if not self.obs.save_replay_buffer():
            self._save_error = "Start the Replay Buffer in OBS and check its connection to RoundLatch."
            return None
        source = _wait_for_new_clip(replay_dir, float(self.cfg.get("engine.clip_wait_sec", 8)), requested_at)
        if not source:
            self._save_error = "OBS did not write a replay. Check the OBS replay folder and available space."
            return None
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        if not ffmpeg:
            return source
        if ranges is not None:
            timeline = []
            trimmed = media.trim_replay(ffmpeg, source, out_path, replay_end, ranges, self.cfg, timeline)
            if trimmed:
                self.last_saved_spans = tuple(timeline)
                return trimmed
        duration = media.probe_duration(ffmpeg, source)
        if duration > 0:
            self.last_saved_spans = ((replay_end - duration, replay_end),)
        return source

    def status(self) -> dict:
        return {"backend": "obs", "capturing": self.obs.replay_buffer_active(),
                "encoder": "obs", "obs_connected": self.obs.connected(), "save_error": self._save_error}


# ───────── shared utilities ─────────
def _encoders_text(ffmpeg: str) -> str:
    try:
        r = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                          capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW)
        return r.stdout or ""
    except Exception:
        return ""


def _process_running(name: str) -> bool:
    """Check through Windows without launching a subprocess for each poll."""
    if sys.platform != "win32":
        return False
    from .winprocess import is_running
    return is_running(name)


def _wait_for_new_clip(replay_dir: Path, timeout: float, requested_at: float) -> Path | None:
    """Poll an OBS output dir for a freshly written video (OBS backend)."""
    start = time.time()
    while time.time() < start + timeout:
        time.sleep(0.5)
        try:
            cands = [f for f in replay_dir.iterdir()
                     if f.is_file() and f.suffix.lower() in (".mp4", ".mkv", ".mov")
                     and f.stat().st_mtime >= requested_at]
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
