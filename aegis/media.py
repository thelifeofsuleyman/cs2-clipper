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


def _run(args: list[str], timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, errors="replace", timeout=timeout,
        creationflags=_NO_WINDOW,
    )


def probe_duration(ffmpeg: str, video: Path) -> float:
    """Duration in seconds via ffprobe (falls back to 0 on failure)."""
    return stream_info(ffmpeg, video)[0]


def stream_info(ffmpeg: str, video: Path) -> tuple[float, bool]:
    ffprobe = Path(ffmpeg).with_name("ffprobe" + (".exe" if sys.platform == "win32" else ""))
    probe = str(ffprobe) if ffprobe.is_file() else shutil.which("ffprobe")
    try:
        if probe:
            r = _run([probe, "-v", "error", "-print_format", "json",
                      "-show_format", "-show_streams", str(video)], timeout=8)
            if r.returncode == 0:
                info = json.loads(r.stdout)
                duration = float(info.get("format", {}).get("duration", 0) or 0)
                return duration, any(s.get("codec_type") == "audio" for s in info.get("streams", []))
        r = _run([ffmpeg, "-hide_banner", "-i", str(video)], timeout=8)
        stamp = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
        duration = (int(stamp[1]) * 3600 + int(stamp[2]) * 60 + float(stamp[3])) if stamp else 0.0
        return duration, bool(re.search(r"Stream .*?: Audio:", r.stderr))
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0, False


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
    performance = bool(cfg.get("recording.prioritize_game_fps", True))
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    cmd += recorder.capture_video_args(w, h, fps, encoder, bitrate, method, performance)
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


def reencode_to_fit(ffmpeg: str | None, video: Path, max_mb: float) -> Path | None:
    """Re-encode ``video`` to land under ``max_mb`` (for Discord's 25 MB cap).

    Targets a bitrate from duration and the size budget, leaving ~10% headroom
    for the audio/container. Returns a temp file path, or None if it can't.
    """
    if not ffmpeg:
        return None
    dur = probe_duration(ffmpeg, video) or 30.0
    target_bits = max_mb * 8 * 1024 * 1024 * 0.9
    v_kbps = max(int(target_bits / dur / 1000) - 128, 300)  # reserve 128k audio
    out = video.with_name(f"{video.stem}__fit{int(max_mb)}mb.mp4")
    log(f"Re-encoding {video.name} to ~{max_mb} MB ({v_kbps}k video)")
    r = _run([ffmpeg, "-y", "-i", str(video),
              "-c:v", "libx264", "-b:v", f"{v_kbps}k",
              "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k",
              "-movflags", "+faststart", str(out)])
    if r.returncode == 0 and out.exists() and out.stat().st_size <= max_mb * 1024 * 1024:
        return out
    log(f"Re-encode did not fit the size budget for {video.name}")
    return out if (r.returncode == 0 and out.exists()) else None


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
