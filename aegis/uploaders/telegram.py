"""Telegram uploader (sendVideo).

Carries over the original clipper's Telegram path. Telegram's bot file limit is
generous (2 GB), so NVENC clips upload as-is with no re-encode needed.
"""
from __future__ import annotations

from pathlib import Path

import requests

from .base import Uploader, UploadResult


class TelegramUploader(Uploader):
    name = "telegram"

    def send(self, clip: Path, caption: str) -> UploadResult:
        token = self.cfg.get("uploads.telegram.bot_token")
        chat_id = self.cfg.get("uploads.telegram.chat_id")
        if not (token and chat_id):
            return UploadResult(False, "not configured")
        try:
            with clip.open("rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendVideo",
                    data={
                        "chat_id": chat_id,
                        "caption": caption,
                        "supports_streaming": True,
                    },
                    files={"video": (clip.name, f, "video/mp4")},
                    timeout=300,
                )
        except Exception as e:
            return UploadResult(False, str(e))
        if r.ok:
            return UploadResult(True)
        return UploadResult(False, f"HTTP {r.status_code}: {r.text[:120]}")
