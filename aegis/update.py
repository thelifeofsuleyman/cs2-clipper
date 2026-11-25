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

import hashlib
import re
import shutil
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import requests

from . import __version__
from .config import Config
from .log import log

_REPO = "thelifeofsuleyman/cs2-clipper"
_RELEASES = f"https://github.com/{_REPO}/releases"
_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
_INSTALLER = "AegisClipper-Setup.exe"
_MAX_INSTALLER_BYTES = 512 * 1024 * 1024


@dataclass
class UpdateInfo:
    version: str
    notes: str
    asset_url: str          # browser_download_url of the setup .exe
    html_url: str           # release page (fallback for source installs)
    digest: str = ""
    size: int = 0

    def as_dict(self) -> dict:
        return {"version": self.version, "notes": self.notes,
                "asset_url": self.asset_url, "html_url": self.html_url}


@dataclass(frozen=True)
class ReleaseCheck:
    info: UpdateInfo | None = None
    error: str = ""
    retry_at: int | None = None


class ReleaseChecker:
    """Share one release lookup across dashboard loads and install clicks."""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._lock = threading.Lock()
        self._result: ReleaseCheck | None = None
        self._completed = 0.0

    def check(self, *, manual: bool = False) -> ReleaseCheck:
        with self._lock:
            if self._result is not None:
                if self._result.retry_at is not None:
                    if time.time() < self._result.retry_at:
                        return self._result
                else:
                    lifetime = 30 if manual or self._result.error else 300
                    if time.monotonic() - self._completed < lifetime:
                        return self._result
            self._result = _fetch_release(self._cfg)
            self._completed = time.monotonic()
            return self._result


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
    """One-shot release lookup for callers outside the dashboard."""
    global _last_error
    result = _fetch_release(cfg)
    _last_error = result.error
    return result.info


def _fetch_release(cfg: Config) -> ReleaseCheck:
    repo = cfg.get("update.repo", "")
    if repo != _REPO:
        return ReleaseCheck(error="Automatic updates require the official release repository.")
    try:
        r = requests.get(_API, timeout=8, allow_redirects=False,
                         headers={"Accept": "application/vnd.github+json"})
        if r.status_code in (403, 429) and (r.status_code == 429
                or r.headers.get("X-RateLimit-Remaining") == "0"
                or r.headers.get("Retry-After")
                or "rate limit" in (r.text or "").lower()):
            return ReleaseCheck(error="GitHub rate limit reached.", retry_at=_rate_limit_reset(r.headers))
        if r.status_code != 200:
            return ReleaseCheck(error=f"GitHub returned HTTP {r.status_code}.")
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        log(f"Update check failed: {e}")
        return ReleaseCheck(error="Could not reach GitHub.")

    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        return ReleaseCheck(error="Unexpected release metadata.")
    tag = data.get("tag_name", "")
    if not isinstance(tag, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or not is_newer(tag):
        return ReleaseCheck()

    expected_url = f"{_RELEASES}/download/{tag}/{_INSTALLER}"
    asset = next((a for a in data["assets"] if isinstance(a, dict) and a.get("name") == _INSTALLER
                  and a.get("browser_download_url") == expected_url), {})
    digest = asset.get("digest") or ""
    size = asset.get("size")
    verified_metadata = (isinstance(digest, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", digest)
                         and type(size) is int and 0 < size <= _MAX_INSTALLER_BYTES)
    info = UpdateInfo(
        version=tag.lstrip("v"),
        notes=body.strip()[:4000] if isinstance(body := data.get("body"), str) else "",
        asset_url=expected_url if verified_metadata else "",
        html_url=f"{_RELEASES}/tag/{tag}",
        digest=digest if verified_metadata else "",
        size=size if verified_metadata else 0,
    )
    log(f"Update available: {info.version}")
    return ReleaseCheck(info=info)


def _rate_limit_reset(headers) -> int:
    now = int(time.time())
    retry = headers.get("Retry-After", "")
    reset = headers.get("X-RateLimit-Reset", "")
    deadlines = []
    if re.fullmatch(r"[0-9]{1,8}", retry) and int(retry) > 0:
        deadlines.append(now + int(retry))
    if headers.get("X-RateLimit-Remaining") == "0" and re.fullmatch(r"[0-9]{1,12}", reset):
        if int(reset) > now:
            deadlines.append(int(reset))
    return max(deadlines, default=now + 60)


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
    import tempfile

    directory = None
    try:
        directory = Path(tempfile.mkdtemp(prefix="AegisClipper-update-"))
        dest = directory / _INSTALLER
        total = info.size
        if (info.asset_url != f"{_RELEASES}/download/v{info.version}/{_INSTALLER}"
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", info.version)
                or not 0 < total <= _MAX_INSTALLER_BYTES
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", info.digest)):
            raise ValueError("Unverified installer metadata")
        with requests.get(info.asset_url, stream=True, timeout=(8, 30), allow_redirects=False) as initial:
            location = initial.headers.get("Location", "")
            target = urlsplit(location)
            if (initial.status_code not in (302, 303, 307, 308)
                    or target.scheme != "https"
                    or target.netloc not in {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}):
                raise ValueError("Unexpected installer download location")
        with requests.get(location, stream=True, timeout=(8, 30), allow_redirects=False) as r:
            if r.status_code != 200:
                raise IOError("GitHub could not deliver the installer")
            _set_progress(total=total)
            done = 0
            digest = hashlib.sha256()
            with dest.open("xb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    done += len(chunk)
                    if done > total:
                        raise IOError("Installer exceeds the published size")
                    digest.update(chunk)
                    f.write(chunk)
                    pct = round(done / total * 100, 1) if total else 0.0
                    _set_progress(downloaded=done, pct=pct)
        if done != total or f"sha256:{digest.hexdigest()}" != info.digest:
            raise IOError("Installer failed SHA-256 verification")
        _set_progress(state="installing", pct=100.0, detail="installing")
        log("Verified update downloaded. Starting installer.")
        _launch_installer_and_exit(str(dest))
    except Exception as e:
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        log(f"Update download failed: {e}")
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
