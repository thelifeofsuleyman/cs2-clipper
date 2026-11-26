"""ffmpeg helpers: locate the binary, make thumbnails, re-encode, montage.

ffmpeg is the one native dependency. We resolve it from (in order) the config
override, a copy bundled next to the program, then PATH. If it's missing the
helpers degrade gracefully — thumbnails are skipped, montage reports an error —
so the core clip→upload path never depends on ffmpeg being present.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import paths
from .log import log

# Hide the console window ffmpeg would otherwise pop on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def resolve_ffmpeg(override: str = "") -> str | None:
    """Find the ffmpeg binary across every layout we ship in.

    PyInstaller 6 puts bundled binaries in an `_internal\\` subfolder (exposed at
    runtime as sys._MEIPASS), NOT next to the .exe — so we must check there first,
    then next to the exe, then PATH. Missing this is why a frozen build reported
    "ffmpeg missing" even though it was bundled.
    """
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if override and Path(override).exists():
        return override

    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)        # PyInstaller bundle dir
    if meipass:
        candidates.append(Path(meipass) / name)
    exe_dir = Path(sys.executable).resolve().parent  # install dir of the .exe
    candidates += [exe_dir / name, exe_dir / "_internal" / name]
    candidates.append(Path(sys.argv[0]).resolve().parent / name)  # dev / script run

    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            continue
    return shutil.which("ffmpeg")


class ExportPaused(Exception):
    """The match started before a background export finished."""


def _run(args: list[str], timeout: float = 120, *, background: bool = False, pause=None) -> subprocess.CompletedProcess:
    priority = subprocess.BELOW_NORMAL_PRIORITY_CLASS if background and sys.platform == "win32" else 0
    if pause is not None:
        if pause():
            raise ExportPaused
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              errors="replace", creationflags=_NO_WINDOW | priority) as process:
            from . import winjob
            winjob.guard(process)
            deadline = time.monotonic() + timeout
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(args, timeout)
                    if pause():
                        raise ExportPaused
                    try:
                        stdout, stderr = process.communicate(timeout=min(0.75, remaining))
                        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
                    except subprocess.TimeoutExpired:
                        continue
            except BaseException:
                process.kill()
                process.communicate()
                raise
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace", timeout=timeout,
        creationflags=_NO_WINDOW | priority,
    )


def probe_duration(ffmpeg: str, video: Path) -> float:
    """Duration in seconds via ffprobe (falls back to 0 on failure)."""
    return stream_info(ffmpeg, video)[0]


def mux_speaker_audio(video_args: list[str], wav: Path, output: list[str]) -> subprocess.CompletedProcess:
    return _run([*video_args, "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "apad",
                 "-shortest", *output], timeout=20)


def stream_info(ffmpeg: str, video: Path) -> tuple[float, bool]:
    duration, audio_tracks = _stream_details(ffmpeg, video)
    return duration, bool(audio_tracks)


def _stream_details(ffmpeg: str, video: Path) -> tuple[float, int]:
    ffprobe = Path(ffmpeg).with_name("ffprobe" + (".exe" if sys.platform == "win32" else ""))
    probe = str(ffprobe) if ffprobe.is_file() else shutil.which("ffprobe")
    try:
        if probe:
            r = _run([probe, "-v", "error", "-print_format", "json",
                      "-show_format", "-show_streams", str(video)], timeout=8)
            if r.returncode == 0:
                info = json.loads(r.stdout)
                duration = float(info.get("format", {}).get("duration", 0) or 0)
                return duration, sum(s.get("codec_type") == "audio" for s in info.get("streams", []))
        r = _run([ffmpeg, "-hide_banner", "-i", str(video)], timeout=8)
        stamp = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        duration = (int(stamp[1]) * 3600 + int(stamp[2]) * 60 + float(stamp[3])) if stamp else 0.0
        return duration, len(re.findall(r"Stream .*?: Audio:", r.stderr))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0, 0


def quality_encode_args(ffmpeg: str, cfg) -> list[str]:
    """Encoder args for a quality-based re-encode (polish, montage). Uses the
    detected GPU encoder so 'baking' a clip/montage takes seconds, not minutes;
    falls back to a fast CPU preset. Quality-targeted (CQ/CRF), not bitrate."""
    from . import recorder
    enc = recorder.pick_encoder(recorder._encoders_text(ffmpeg),
                                cfg.get("recording.encoder", "auto"))
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23",
                "-pix_fmt", "yuv420p"]
    if enc == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp",
                "-qp_i", "23", "-qp_p", "23", "-pix_fmt", "yuv420p"]
    if enc == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "faster", "-global_quality", "23",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


def trim_replay(ffmpeg: str, source: Path, destination: Path, replay_end: float,
                ranges: list[tuple[float, float]], cfg,
                timeline: list[tuple[float, float]] | None = None) -> Path | None:
    duration, audio_tracks = _stream_details(ffmpeg, source)
    replay_start = replay_end - duration
    edits = [(max(0.0, start - replay_start), min(duration, stop - replay_start))
             for start, stop in ranges]
    edits = [(start, stop) for start, stop in edits if stop - start >= 0.1]
    if not edits:
        log("OBS replay contained no footage from the kill windows")
        return None

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-filter_complex_threads", "2"]
    streams = []
    for index, (start, stop) in enumerate(edits):
        cmd += ["-ss", f"{start:.3f}", "-t", f"{stop - start:.3f}", "-threads", "2", "-i", str(source)]
        streams.append(f"[{index}:v:0]" + "".join(f"[{index}:a:{track}]" for track in range(audio_tracks)))
    audio_labels = [f"[a{track}]" for track in range(audio_tracks)]
    output_labels = "[v]" + "".join(audio_labels)
    graph = "".join(streams) + f"concat=n={len(edits)}:v=1:a={audio_tracks}" + output_labels
    cmd += ["-filter_complex", graph, "-map", "[v]"]
    for label in audio_labels:
        cmd += ["-map", label]
    if audio_tracks:
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    end = ["-movflags", "+faststart", str(destination)]
    encode = quality_encode_args(ffmpeg, cfg)
    fallback = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-threads", "2", "-pix_fmt", "yuv420p"]
    for settings in (encode, fallback):
        try:
            result = _run([*cmd, *settings, *end], timeout=90)
            if result.returncode == 0 and destination.exists() and destination.stat().st_size:
                if timeline is not None:
                    timeline.extend((replay_start + start, replay_start + stop) for start, stop in edits)
                return destination
            log(f"OBS highlight trim failed: {result.stderr[-200:]}")
        except (OSError, subprocess.SubprocessError) as exc:
            log(f"OBS highlight trim failed: {exc}")
    destination.unlink(missing_ok=True)
    return None


def trim_clip(ffmpeg: str, source: Path, destination: Path, start: float, end: float) -> bool:
    """Accurately seek and encode a selected range, including all audio tracks."""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
           "-protocol_whitelist", "file,pipe", "-threads", "2", "-ss", f"{start:.3f}",
           "-i", str(source), "-t", f"{end - start:.3f}",
           "-map", "0:v:0", "-map", "0:a?", "-map_chapters", "-1",
           "-filter_threads", "1", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "2",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
           str(destination)]
    try:
        result = _run(cmd, timeout=150, background=True)
        if result.returncode == 0 and destination.is_file() and destination.stat().st_size > 0:
            return True
        log(f"Clip trim failed: {result.stderr[-200:]}")
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"Clip trim failed: {exc}")
    return False


def make_test_clip(ffmpeg: str | None, out_path: Path, seconds: int = 5) -> Path | None:
    """Generate a short synthetic clip (test pattern + tone).

    Lets the wizard verify the full catalog + upload pipeline end-to-end without
    needing CS2 open or a real capture. Returns the path, or None if ffmpeg is
    missing or the encode fails.
    """
    if not ffmpeg:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    r = _run([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=1280x720:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out_path),
    ])
    return out_path if (r.returncode == 0 and out_path.exists()) else None


def _capture_once(ffmpeg: str, out_path: Path, seconds: int, cfg, method: str, encoder: str) -> bool:
    from . import recorder
    w, h, fps, bitrate = recorder.capture_options(cfg, encoder)
    performance = cfg.game_fps_priority()
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    cmd += recorder.capture_video_args(w, h, fps, encoder, bitrate, method, performance,
                                       bool(cfg.get("recording.compact_video")))
    cmd += ["-t", str(seconds), "-movflags", "+faststart", str(out_path)]

    log(f"Screen capture test via {method} ({fps} fps, {encoder}, {seconds}s)")
    try:
        r = _run(cmd, timeout=seconds + 8)
    except (OSError, subprocess.SubprocessError) as e:
        log(f"Capture via {method} / {encoder} failed: {e}")
        return False
    ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 1024
    if not ok:
        log(f"Capture via {method} failed: {(r.stderr or '')[-200:]}")
    return ok


def capture_screen_test(ffmpeg: str | None, out_path: Path, seconds: int, cfg) -> str | None:
    """Record `seconds` of the real screen, trying the configured capture method
    first and falling back to the other one. Returns the method that worked
    ('ddagrab'/'gdigrab') so the caller can remember it, or None if both failed."""
    if not ffmpeg:
        return None
    from .recorder import capture_candidates
    for method, encoder in capture_candidates(ffmpeg, cfg):
        if _capture_once(ffmpeg, out_path, seconds, cfg, method, encoder):
            return "ddagrab" if method == "ddagrab-d3d11" else method
    out_path.unlink(missing_ok=True)
    return None


def make_thumbnail(ffmpeg: str | None, video: Path, clip_id: str) -> Path | None:
    """Grab a frame ~2s in as a JPEG. Returns the thumb path or None."""
    if not ffmpeg:
        return None
    out = paths.thumbs_dir() / f"{clip_id}.jpg"
    r = _run([ffmpeg, "-y", "-ss", "2", "-i", str(video),
              "-frames:v", "1", "-vf", "scale=480:-1", str(out)])
    if r.returncode == 0 and out.exists():
        return out
    # Retry from the very start for clips shorter than 2s.
    r = _run([ffmpeg, "-y", "-i", str(video),
              "-frames:v", "1", "-vf", "scale=480:-1", str(out)])
    return out if (r.returncode == 0 and out.exists()) else None


def reencode_to_fit(ffmpeg: str | None, video: Path, out: Path, max_bytes: int, *,
                    pause=None, window: tuple[float, float] | None = None) -> bool:
    """Make a shareable MP4 within a byte cap. The caller owns the scratch directory."""
    if not ffmpeg:
        return False
    duration, audio = stream_info(ffmpeg, video)
    if duration <= 0:
        return False
    seek = []
    length = []
    if window is not None:
        start, end = window
        if not 0 <= start < end <= duration + 0.1 or min(end, duration) - start < 0.249:
            return False
        duration = min(end, duration) - start
        seek = ["-ss", f"{start:.3f}"]
        length = ["-t", f"{duration:.3f}"]
    audio_kbps = 128 if audio else 0
    budget_kbps = max_bytes * 8 / duration / 1000
    for headroom in (0.90, 0.76):
        video_kbps = int(budget_kbps * headroom) - audio_kbps
        if video_kbps < 150:
            return False
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-protocol_whitelist", "file,pipe", "-threads", "2", *seek, "-i", str(video), *length,
               "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1", "-map_chapters", "-1",
               "-filter_threads", "1"]
        if video_kbps < 2200:
            # Preserve aspect ratio and never upscale a small source.
            cmd += ["-vf", "scale=w='min(iw,1280)':h='min(ih,720)':"
                    "force_original_aspect_ratio=decrease:force_divisible_by=2"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-threads", "2", "-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps}k",
                "-bufsize", f"{video_kbps * 2}k", "-c:a", "aac", "-b:a", "128k", "-ac", "2",
                "-movflags", "+faststart", str(out)]
        try:
            kwargs = {"pause": pause} if pause is not None else {}
            result = _run(cmd, timeout=110, background=True, **kwargs)
            if result.returncode != 0:
                log(f"Could not encode a share copy: {result.stderr[-200:]}")
                return False
            if out.is_file() and 0 < out.stat().st_size <= max_bytes:
                return True
        except (OSError, subprocess.SubprocessError) as exc:
            log(f"Could not encode a share copy: {exc}")
            return False
    return False


def build_montage(
    ffmpeg: str | None,
    clips: list[Path],
    out_path: Path,
    music: Path | None = None,
    vertical: bool = False,
    encode_args: list[str] | None = None,
) -> Path | None:
    """Concatenate ``clips`` (re-encoded to a common format) into one file.

    Re-encode-concat (not stream-copy) because clips may differ in resolution
    after Discord-fit passes. Optional background music replaces clip audio;
    ``vertical`` produces a padded 1080x1920 mobile cut.
    """
    if not ffmpeg or not clips:
        return None

    scale = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
        if vertical else
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    )

    args: list[str] = [ffmpeg, "-y"]
    for c in clips:
        args += ["-i", str(c)]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]

    n = len(clips)
    filt = "".join(
        f"[{i}:v]{scale},setsar=1,fps=60,format=yuv420p,setpts=PTS-STARTPTS[v{i}];"
        for i in range(n)
    )
    if music:
        filt += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]"
        maps = ["-map", "[vout]", "-map", f"{n}:a", "-shortest"]
    else:
        streams = [stream_info(ffmpeg, c) for c in clips]
        if any(audio for _, audio in streams):
            for i, (duration, audio) in enumerate(streams):
                if audio:
                    filt += (f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                             f"asetpts=PTS-STARTPTS[a{i}];")
                else:
                    filt += f"anullsrc=r=48000:cl=stereo:d={max(.001, duration):.3f}[a{i}];"
            filt += "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]"
            maps = ["-map", "[vout]", "-map", "[aout]"]
        else:
            filt += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]"
            maps = ["-map", "[vout]"]

    venc = encode_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    log(f"Building montage from {n} clip(s) -> {out_path.name}")
    base = [*args, "-filter_complex", filt, *maps]
    options = [venc]
    if "libx264" not in venc:
        options.append(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])
    for encoder in options:
        try:
            r = _run([*base, *encoder, "-c:a", "aac", "-b:a", "192k",
                      "-movflags", "+faststart", str(out_path)], timeout=300)
            if r.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                return out_path
            log(f"Montage build failed ({encoder[1]}): {r.stderr[-300:]}")
        except (OSError, subprocess.SubprocessError) as e:
            log(f"Montage build failed ({encoder[1]}): {e}")
    out_path.unlink(missing_ok=True)
    return None
