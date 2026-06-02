"""In-app updater — checks GitHub Releases and applies updates in place.

Flow:
  check()  -> ask GitHub for the latest release, compare its tag to __version__.
  apply()  -> download the setup .exe asset, run it silently, then exit so the
              installer can replace the (now-unlocked) program files.

Because all user state lives in %APPDATA% (see paths.py) and the Inno installer
upgrades in place by AppId, an update never disturbs config or the clip catalog —
the user is never sent back through the setup wizard.

When running from source (not a frozen build) there's no installer to run, so
apply() just opens the release page in the browser instead.
"""
from __future__ import annotations

import re
import sys
import threading
import webbrowser
from dataclasses import dataclass

import requests

from . import __version__
from .config import Config
from .log import log

_API = "https://api.github.com/repos/{repo}/releases/latest"


@dataclass
class UpdateInfo:
    version: str
    notes: str
    asset_url: str          # browser_download_url of the setup .exe
    html_url: str           # release page (fallback for source installs)

    def as_dict(self) -> dict:
        return {"version": self.version, "notes": self.notes,
                "asset_url": self.asset_url, "html_url": self.html_url}


def _parse(v: str) -> tuple:
    """'v2.10.1' -> (2, 10, 1); non-numeric parts drop to 0 so compares are total."""
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return _parse(remote) > _parse(local)


def check(cfg: Config) -> UpdateInfo | None:
    """Return UpdateInfo if a newer release exists, else None. Never raises."""
    repo = cfg.get("update.repo", "")
    if not repo or "OWNER/REPO" in repo:
        return None
    try:
        r = requests.get(_API.format(repo=repo), timeout=8,
                         headers={"Accept": "application/vnd.github+json"})
        if not r.ok:
            return None
        data = r.json()
    except Exception as e:
        log(f"Update check failed: {e}")
        return None

    tag = data.get("tag_name", "")
    if not is_newer(tag):
        return None

    asset = next((a["browser_download_url"] for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), "")
    info = UpdateInfo(
        version=tag.lstrip("v"),
        notes=(data.get("body") or "").strip()[:4000],
        asset_url=asset,
        html_url=data.get("html_url", ""),
    )
    log(f"Update available: {info.version}")
    return info


def apply(info: UpdateInfo) -> dict:
    """Download and launch the installer silently, then exit. Returns a status
    dict if it could not proceed (so the API can report it)."""
    frozen = getattr(sys, "frozen", False)
    if not frozen or not info.asset_url:
        # Dev build or no installer asset: just open the release page.
        if info.html_url:
            webbrowser.open(info.html_url)
        return {"ok": False, "detail": "opened release page (no in-place update for source builds)"}

    import os
    import subprocess
    import tempfile

    try:
        dest = os.path.join(tempfile.gettempdir(), "AegisClipper-Setup.exe")
        with requests.get(info.asset_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
    except Exception as e:
        log(f"Update download failed: {e}")
        return {"ok": False, "detail": str(e)}

    log("Update downloaded — launching installer and exiting.")
    # /SILENT installs without prompts; CLOSEAPPLICATIONS+RESTARTAPPLICATIONS lets
    # Inno close this running app, swap files, and relaunch the new version.
    try:
        subprocess.Popen([dest, "/SILENT", "/CLOSEAPPLICATIONS",
                          "/RESTARTAPPLICATIONS", "/NORESTART"])
    except Exception as e:
        return {"ok": False, "detail": str(e)}

    # Give the installer a moment to start, then quit so files unlock.
    threading.Timer(1.5, lambda: os._exit(0)).start()
    return {"ok": True, "detail": "installing update…"}
