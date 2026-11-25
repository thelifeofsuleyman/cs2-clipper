"""Discord uploader (incoming webhook).

Webhooks are the easiest target to set up — the user pastes one URL, no bot or
OAuth. The catch is the 25 MB attachment cap (50 MB with a boosted server). CS2
NVENC clips often exceed that, so when a clip is too big we transparently
re-encode a smaller copy with ffmpeg to fit before posting. If it still won't
fit (or ffmpeg is missing), we report a clear error rather than failing silently.
"""
from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import requests

from .. import media
from .base import Uploader, UploadResult


class DiscordUploader(Uploader):
    name = "discord"

    def send(self, clip: Path, caption: str) -> UploadResult:
        url = self.cfg.get("uploads.discord.webhook_url")
        if not url:
            return UploadResult(False, "not configured")
        try:
            target = urlsplit(url)
            valid = (target.scheme == "https" and target.netloc in {"discord.com", "discordapp.com"}
                     and re.fullmatch(r"/api/(?:v[0-9]+/)?webhooks/[0-9]+/[A-Za-z0-9_.-]+", target.path))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            return UploadResult(False, "Enter a Discord HTTPS webhook URL")
        max_mb = float(self.cfg.get("uploads.discord.max_mb", 25))

        max_bytes = int(max_mb * 1024 * 1024)
        if clip.stat().st_size <= max_bytes:
            return self._post(url, clip, caption)
        ffmpeg = media.resolve_ffmpeg(self.cfg.get("ffmpeg_path", ""))
        with TemporaryDirectory(prefix="aegis-discord-") as scratch:
            fitted = Path(scratch) / (clip.stem + "-share.mp4")
            if not media.reencode_to_fit(ffmpeg, clip, fitted, max_bytes):
                return UploadResult(False, "Could not fit the clip under the configured size limit")
            return self._post(url, fitted, caption)

    def _post(self, url: str, to_send: Path, caption: str) -> UploadResult:
        try:
            with to_send.open("rb") as f:
                r = requests.post(
                    url,
                    data={"content": caption},
                    files={"file": (to_send.name, f, "video/mp4")},
                    timeout=300,
                    allow_redirects=False,
                )
        except (OSError, requests.RequestException):
            return UploadResult(False, "Could not send the clip to Discord")

        if 200 <= r.status_code < 300:
            return UploadResult(True)
        return UploadResult(False, f"Discord returned HTTP {r.status_code}")
