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


_last_error = ""


def get_last_error() -> str:
    """Why the most recent check() couldn't determine an update (empty if fine)."""
    return _last_error


def check(cfg: Config) -> UpdateInfo | None:
    """Return UpdateInfo if a newer release exists, else None. Never raises.
    Records a human reason in get_last_error() when a check can't complete."""
    global _last_error
    _last_error = ""
    repo = cfg.get("update.repo", "")
    if not repo or "OWNER/REPO" in repo:
        _last_error = "update repo not configured"
        return None
    try:
        r = requests.get(_API.format(repo=repo), timeout=8,
                         headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 403 and "rate limit" in (r.text or "").lower():
            _last_error = "GitHub rate limit reached — try again in a few minutes"
            return None
        if not r.ok:
            _last_error = f"GitHub returned HTTP {r.status_code}"
            return None
        data = r.json()
    except Exception as e:
        _last_error = "couldn't reach GitHub"
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


# Live progress so the UI can show a bar during the (multi-minute) download.
_progress = {"state": "idle", "downloaded": 0, "total": 0, "pct": 0.0, "detail": ""}
_progress_lock = threading.Lock()


def get_progress() -> dict:
    with _progress_lock:
        return dict(_progress)


def _set_progress(**kw) -> None:
    with _progress_lock:
        _progress.update(kw)


def start_apply(info: UpdateInfo) -> dict:
    """Begin the update on a background thread and return immediately so the UI
    can poll get_progress(). Source builds (not frozen) just open the page."""
    frozen = getattr(sys, "frozen", False)
    if not frozen or not info.asset_url:
        if info.html_url:
            webbrowser.open(info.html_url)
        _set_progress(state="manual", detail="opened release page")
        return {"ok": False, "detail": "opened release page (no in-place update for source builds)"}

    with _progress_lock:
        if _progress["state"] in ("downloading", "installing"):
            return {"ok": True, "detail": "already in progress"}
        _progress.update(state="downloading", downloaded=0, total=0, pct=0.0, detail="")

    threading.Thread(target=_download_and_install, args=(info,), daemon=True).start()
    return {"ok": True, "detail": "started"}


def _download_and_install(info: UpdateInfo) -> None:
    import os
    import subprocess
    import tempfile

    try:
        dest = os.path.join(tempfile.gettempdir(), "AegisClipper-Setup.exe")
        with requests.get(info.asset_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0) or 0)
            _set_progress(total=total)
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    pct = round(done / total * 100, 1) if total else 0.0
                    _set_progress(downloaded=done, pct=pct)
        # Guard against a truncated download before we run an installer.
        if total and done != total:
            raise IOError(f"incomplete download ({done}/{total} bytes)")
    except Exception as e:
        log(f"Update download failed: {e}")
        _set_progress(state="error", detail=str(e)[:200])
        return

    _set_progress(state="installing", pct=100.0, detail="installing")
    log("Update downloaded — exiting so the installer can replace files.")
    try:
        _launch_installer_and_exit(dest)
    except Exception as e:
        _set_progress(state="error", detail=str(e)[:200])


def _launch_installer_and_exit(installer: str) -> None:
    """Launch the installer and exit immediately so it can replace our files.

    Kept deliberately minimal after repeated update breakage:
    - Launch the installer by its ABSOLUTE path (no cmd/PowerShell), so there's
      no PATH lookup that can fail with "WinError 2: file not found".
    - Exit instantly (os._exit). The installer extracts for a few seconds first,
      by which time we (and ffmpeg, via the Job Object) are already gone, so the
      file-replace step isn't blocked.
    - /CLOSEAPPLICATIONS is a backstop; the installer's WizardSilent [Run] entry
      relaunches the app once the silent update finishes.
    If the launch itself fails, the exception propagates and the UI shows an
    error instead of leaving the app half-closed.
    """
    import os
    import subprocess

    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(
        [installer, "/SILENT", "/CLOSEAPPLICATIONS", "/NORESTART"],
        creationflags=DETACHED_PROCESS,
        close_fds=True,
    )
    os._exit(0)


# Backwards-compatible alias.
def apply(info: UpdateInfo) -> dict:
    return start_apply(info)
