"""Discord uploader (incoming webhook).

Webhooks are the easiest target to set up — the user pastes one URL, no bot or
OAuth. The catch is the 25 MB attachment cap (50 MB with a boosted server). CS2
NVENC clips often exceed that, so when a clip is too big we transparently
re-encode a smaller copy with ffmpeg to fit before posting. If it still won't
fit (or ffmpeg is missing), we report a clear error rather than failing silently.
"""
from __future__ import annotations

from pathlib import Path

import requests

from .. import media
from ..log import log
from .base import Uploader, UploadResult


class DiscordUploader(Uploader):
    name = "discord"

    def send(self, clip: Path, caption: str) -> UploadResult:
        url = self.cfg.get("uploads.discord.webhook_url")
        if not url:
            return UploadResult(False, "not configured")
        max_mb = float(self.cfg.get("uploads.discord.max_mb", 25))

        to_send = clip
        temp: Path | None = None
        size_mb = clip.stat().st_size / (1024 * 1024)
        if size_mb > max_mb:
            ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
            fitted = media.reencode_to_fit(ffmpeg, clip, max_mb)
            if fitted is None:
                return UploadResult(False, f"{size_mb:.0f} MB > {max_mb:.0f} MB and could not re-encode")
            to_send, temp = fitted, fitted
            if to_send.stat().st_size / (1024 * 1024) > max_mb:
                _cleanup(temp)
                return UploadResult(False, f"still over {max_mb:.0f} MB after re-encode")

        try:
            with to_send.open("rb") as f:
                r = requests.post(
                    url,
                    data={"content": caption},
                    files={"file": (to_send.name, f, "video/mp4")},
                    timeout=300,
                )
        except Exception as e:
            return UploadResult(False, str(e))
        finally:
            _cleanup(temp)

        if r.ok:
            return UploadResult(True)
        return UploadResult(False, f"HTTP {r.status_code}: {r.text[:120]}")


def _cleanup(p: Path | None) -> None:
    if p is None:
        return
    try:
        p.unlink()
    except Exception as e:
        log(f"Could not remove temp file {p}: {e}")
