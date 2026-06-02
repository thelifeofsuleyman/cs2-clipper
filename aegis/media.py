"""ffmpeg helpers: locate the binary, make thumbnails, re-encode, montage.

ffmpeg is the one native dependency. We resolve it from (in order) the config
override, a copy bundled next to the program, then PATH. If it's missing the
helpers degrade gracefully — thumbnails are skipped, montage reports an error —
so the core clip→upload path never depends on ffmpeg being present.
"""
from __future__ import annotations

import json
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


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, creationflags=_NO_WINDOW,
    )


def probe_duration(ffmpeg: str, video: Path) -> float:
    """Duration in seconds via ffprobe (falls back to 0 on failure)."""
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists() and shutil.which("ffprobe"):
        ffprobe = "ffprobe"
    try:
        r = _run([ffprobe, "-v", "quiet", "-print_format", "json",
                  "-show_format", str(video)])
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


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


def capture_screen_test(ffmpeg: str | None, out_path: Path, seconds: int, cfg) -> bool:
    """Record `seconds` of the actual screen to out_path, using the configured
    quality preset, capture method, and encoder. Proves the real recorder works
    (ddagrab + GPU encode) without needing a kill in CS2."""
    if not ffmpeg:
        return False
    from . import recorder
    preset = cfg.get("recording.preset", "medium")
    w, h, fps, bitrate = recorder.PRESETS.get(preset, recorder.PRESETS["medium"])
    fps = int(cfg.get("recording.fps", fps) or fps)
    encoder = recorder.pick_encoder(recorder._encoders_text(ffmpeg),
                                    cfg.get("recording.encoder", "auto"))
    use_dda = cfg.get("recording.capture", "ddagrab") != "gdigrab"

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if use_dda:
        chain = f"ddagrab=output_idx=0:framerate={fps},hwdownload,format=bgra"
        if w and h:
            chain += f",scale={w}:{h}"
        chain += ",format=nv12"
        cmd += ["-filter_complex", chain]
    else:
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]
        if w and h:
            cmd += ["-vf", f"scale={w}:{h}"]
    cmd += recorder._encoder_args(encoder, bitrate)
    cmd += ["-t", str(seconds), "-movflags", "+faststart", str(out_path)]

    log(f"Screen capture test ({preset}, {encoder}, {seconds}s)")
    r = _run(cmd)
    if r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        return True
    log(f"Screen capture test failed: {(r.stderr or '')[-200:]}")
    return False


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
) -> Path | None:
    """Concatenate ``clips`` (re-encoded to a common format) into one file.

    Re-encode-concat (not stream-copy) because clips may differ in resolution
    after Discord-fit passes. Optional background music replaces clip audio;
    ``vertical`` produces a 1080x1920 blurred-pad mobile cut.
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
        args += ["-i", str(music)]

    n = len(clips)
    filt = "".join(
        f"[{i}:v]{scale},setsar=1,fps=60[v{i}];" for i in range(n)
    )
    if music:
        filt += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]"
        maps = ["-map", "[vout]", "-map", f"{n}:a", "-shortest"]
    else:
        filt += "".join(f"[v{i}][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]"
        maps = ["-map", "[vout]", "-map", "[aout]"]

    args += ["-filter_complex", filt, *maps,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
             str(out_path)]

    log(f"Building montage from {n} clip(s) -> {out_path.name}")
    r = _run(args)
    if r.returncode == 0 and out_path.exists():
        return out_path
    log(f"Montage build failed: {r.stderr[-300:] if r.stderr else 'unknown error'}")
    return None
