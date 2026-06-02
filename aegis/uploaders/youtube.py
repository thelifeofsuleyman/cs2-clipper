"""YouTube uploader (Data API v3, OAuth 2.0 installed-app flow).

This is the only target that needs real OAuth, so it's the "advanced" option and
never blocks the easy path. Setup, one time:
  1. Create a Google Cloud project, enable "YouTube Data API v3".
  2. Create an OAuth client ID of type *Desktop app*, download client_secrets.json.
  3. Point uploads.youtube.client_secrets at that file in the wizard.

On first upload a browser opens for consent; the resulting token is cached in the
data dir so later uploads are silent. The Google client libraries are optional
deps — if they're not installed we report that instead of crashing import.
"""
from __future__ import annotations

from pathlib import Path

from .. import paths
from ..log import log
from .base import Uploader, UploadResult

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploader(Uploader):
    name = "youtube"

    def send(self, clip: Path, caption: str) -> UploadResult:
        secrets = self.cfg.get("uploads.youtube.client_secrets")
        if not secrets or not Path(secrets).exists():
            return UploadResult(False, "client_secrets.json not set")

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            return UploadResult(
                False,
                "google libs missing (pip install google-api-python-client google-auth-oauthlib)",
            )

        try:
            creds = self._credentials(secrets, Credentials, Request, InstalledAppFlow)
            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {"title": caption[:100] or "CS2 Highlight",
                            "description": caption, "categoryId": "20"},  # 20 = Gaming
                "status": {"privacyStatus": self.cfg.get("uploads.youtube.privacy", "unlisted")},
            }
            media_body = MediaFileUpload(str(clip), chunksize=-1, resumable=True)
            req = youtube.videos().insert(part="snippet,status", body=body, media_body=media_body)
            resp = req.execute()
        except Exception as e:
            return UploadResult(False, str(e)[:120])

        vid = resp.get("id")
        log(f"YouTube upload complete: https://youtu.be/{vid}")
        return UploadResult(True, f"https://youtu.be/{vid}")

    def _credentials(self, secrets, Credentials, Request, InstalledAppFlow):
        """Load cached token, refresh, or run the consent flow once."""
        token_path = paths.data_root() / "youtube_token.json"
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
                creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds
