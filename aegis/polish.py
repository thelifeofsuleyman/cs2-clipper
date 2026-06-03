"""Turn a raw clip into a share-ready video.

Pipeline (each step degrades gracefully — any failure returns the raw clip so a
highlight is never lost):
  1. Pillow composes a designed intro CARD (1080p, transparent): the killer's
     circular Steam avatar, their name, a big "ACE"/"TRIPLE KILL" line, the map,
     and a small Aegis mark.
  2. ffmpeg overlays the card on the first few seconds (fading in/out) and applies
     a fade-in/out to the whole clip.

Pillow is already bundled (the tray icon needs it) so the card composition works
in the frozen app. The ffmpeg filtergraph is built by a pure function so it can
be unit-tested without a GPU.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import media, paths, steam
from .config import Config
from .log import log

KILL_BIG = {1: "KILL", 2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "QUAD KILL", 5: "ACE"}

_WIN_FONTS = {
    "bold": r"C:\Windows\Fonts\arialbd.ttf",
    "black": r"C:\Windows\Fonts\ariblk.ttf",
    "reg": r"C:\Windows\Fonts\arial.ttf",
}


def _font(kind: str, size: int):
    from PIL import ImageFont
    path = _WIN_FONTS.get(kind, _WIN_FONTS["bold"])
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_WIN_FONTS["bold"], size)
        except Exception:
            return ImageFont.load_default()


def make_intro_card(name: str, avatar: Path | None, kills: int,
                    map_name: str, out_png: Path) -> Path | None:
    """Compose the intro overlay PNG. Returns None if Pillow is unavailable."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    try:
        W, H = 1920, 1080
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx = W // 2
        cy = int(H * 0.32)
        R = 110

        # circular avatar with an accent ring
        if avatar and Path(avatar).exists():
            try:
                av = Image.open(avatar).convert("RGBA").resize((R * 2, R * 2))
                mask = Image.new("L", (R * 2, R * 2), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, R * 2, R * 2), fill=255)
                img.paste(av, (cx - R, cy - R), mask)
            except Exception:
                pass
        d.ellipse((cx - R - 5, cy - R - 5, cx + R + 5, cy + R + 5),
                  outline=(255, 90, 60, 255), width=7)

        def centered(text, font, y, fill):
            w = d.textlength(text, font=font)
            d.text((cx - w / 2, y), text, font=font, fill=fill)

        name = (name or "Player").strip()[:24]
        centered(name, _font("bold", 60), cy + R + 26, (255, 255, 255, 255))

        big = KILL_BIG.get(kills, f"{kills} KILLS")
        centered(big, _font("black", 150), cy + R + 110, (255, 90, 60, 255))

        sub = (map_name or "").replace("de_", "").replace("_", " ").upper()
        if sub:
            centered(sub, _font("reg", 44), cy + R + 290, (185, 195, 208, 255))

        # subtle Aegis mark
        centered("▸ AEGIS CLIPPER", _font("bold", 30), int(H * 0.90), (140, 150, 165, 220))

        out_png.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_png)
        return out_png
    except Exception as e:
        log(f"Intro card composition failed: {e}")
        return None


def build_polish_cmd(ffmpeg: str, raw: Path, out: Path, intro_png: Path | None,
                     duration: float, *, fade: bool, intro_seconds: float,
                     encode_args: list[str] | None = None) -> list[str]:
    """ffmpeg command: fade the clip + overlay the intro card for the first
    `intro_seconds` (with its own fade in/out)."""
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw)]
    parts: list[str] = []

    base_filters = []
    if fade:
        base_filters.append("fade=t=in:st=0:d=0.4")
        if duration > 1.2:
            base_filters.append(f"fade=t=out:st={max(0.0, duration - 0.5):.2f}:d=0.5")
    parts.append(f"[0:v]{','.join(base_filters) if base_filters else 'null'}[base0]")
    last = "[base0]"

    if intro_png and Path(intro_png).exists():
        args += ["-i", str(intro_png)]
        # Scale the 1080p card to whatever resolution this clip is (scale2ref),
        # then fade it in/out and overlay it for the first few seconds.
        parts.append("[1:v]format=rgba[card]")
        parts.append("[card][base0]scale2ref=w=iw:h=ih[cards][base1]")
        fin = "fade=t=in:st=0:d=0.3:alpha=1"
        fout = f"fade=t=out:st={max(0.0, intro_seconds - 0.4):.2f}:d=0.4:alpha=1"
        parts.append(f"[cards]{fin},{fout}[intro]")
        parts.append(f"[base1][intro]overlay=0:0:enable='lt(t,{intro_seconds:.2f})'[v]")
        last = "[v]"

    venc = encode_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p"]
    args += [
        "-filter_complex", ";".join(parts),
        "-map", last, "-map", "0:a?",
        *venc,
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out),
    ]
    return args


def polish_clip(cfg: Config, raw: Path, kills: int, map_name: str,
                steam_name: str, steam_id: str) -> Path | None:
    """Produce a polished version of `raw`. Returns the new path, or None if
    polishing is off/unavailable (caller then keeps the raw clip)."""
    if not cfg.get("polish.enabled", True):
        return None
    ffmpeg = media.resolve_ffmpeg(cfg.get("ffmpeg_path", ""))
    if not ffmpeg:
        return None

    duration = media.probe_duration(ffmpeg, raw) or 0.0
    intro_png = None
    if cfg.get("polish.intro", True):
        avatar = steam.fetch_avatar(steam_id) if steam_id else None
        card = paths.data_root() / f"_intro_{raw.stem}.png"
        intro_png = make_intro_card(steam_name, avatar, kills, map_name, card)

    out = raw.with_name(raw.stem + "_clip.mp4")
    cmd = build_polish_cmd(
        ffmpeg, raw, out, intro_png, duration,
        fade=bool(cfg.get("polish.fade", True)),
        intro_seconds=float(cfg.get("polish.intro_seconds", 3.0)),
        encode_args=media.quality_encode_args(ffmpeg, cfg),   # GPU when available
    )
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=media._NO_WINDOW)
    except Exception as e:
        log(f"Clip polish failed to run: {e}")
        return None
    finally:
        if intro_png and Path(intro_png).exists():
            try:
                Path(intro_png).unlink()
            except Exception:
                pass

    if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
        log(f"Polished clip ready: {out.name}")
        return out
    log(f"Clip polish failed: {(r.stderr or '')[-200:]}")
    return None
