# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Aegis Clipper** — a local-first automatic CS2 highlight clipper (an
allstar.gg-style tool that runs entirely on the user's PC). It detects kill
streaks via CS2 Game State Integration, records the moment with its **own
built-in ffmpeg recorder (no OBS required)**, catalogs each clip, serves a web
dashboard, fans clips out to upload targets, and builds montages. v2 grew out of
a single-file script ([clipper.py](clipper.py), now a thin launcher) into the
[aegis/](aegis/) package. It ships as a self-installing Windows `.exe` built by
GitHub Actions.

## Commands

```powershell
# Dev setup
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run
python -m aegis              # full app: system tray + dashboard + setup wizard
python -m aegis --headless   # engine + dashboard, no tray (CI/servers/console)
python -m aegis --port 3500  # override GSI/dashboard port for this run
python clipper.py            # legacy launcher, same as `python -m aegis`

# Build the distributable (from repo root)
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg -Installer
```

There is **no test suite or linter**. To smoke-test without OBS/CS2, use Flask's
test client against `create_app(...)` (see `aegis/web.py`) — POST GSI-shaped JSON
to `/`, GET `/api/clips`, `/api/status`, `/api/detect`, etc. Set
`AEGIS_DATA_DIR` to an absolute path to keep test state out of `%APPDATA%`.

ffmpeg is **not** required to run; thumbnail/montage features detect it and
degrade if absent. The engine + upload path never depend on it.

## Architecture

Data flow, all in one local process:

```
CS2 GSI ─POST /─► engine.handle_payload ─► debounce Timer ─► engine._save_clip
                                                              ├ OBS.save_replay_buffer()
                                                              ├ wait_for_new_clip (poll dir)
                                                              ├ catalog Clip (+thumbnail)
                                                              └ fan_out ─► every enabled Uploader
Browser ─GET /─► dashboard ;  /setup ─► wizard ;  /api/* ─► JSON
```

Things that need reading several files to grasp:

- **One Flask app, two audiences, one port.** [aegis/web.py](aegis/web.py)
  registers `POST /` for CS2's GSI ticks and `GET /` for the dashboard, so the
  existing GSI `.cfg` needs no change. The dashboard/wizard HTML are
  self-contained strings in [aegis/pages.py](aegis/pages.py) (inline CSS/JS, data
  via `/api/*`) — deliberately no template/static files, so PyInstaller has
  nothing to locate after freezing.

- **The engine is the original core, refactored.** [aegis/engine.py](aegis/engine.py)
  keeps the delta-based kill detection (GSI sends *cumulative* kills; a decrease =
  new match and is swallowed; `-1` sentinel = uninitialized so connecting
  mid-match never fires) and the debounce bundling (one `threading.Timer`, reset
  per kill, fires `_save_clip`). All shared state is under `self._lock` because
  Flask is threaded and the Timer runs on its own thread. `_save_clip` delegates
  to `self.recorder.save(seconds, out_path)` — it doesn't know or care which
  backend recorded.

- **Recording is a pluggable backend.** [aegis/recorder.py](aegis/recorder.py)
  defines `Recorder` with two impls chosen by `recording.backend`:
  `BuiltinRecorder` (default, no OBS) runs ffmpeg continuously capturing the
  screen via Desktop Duplication (`ddagrab`, sees fullscreen games) into a
  **rolling buffer of mpegts segments** (segment muxer + `-segment_wrap`); on a
  kill it stream-copies the newest segments into one clip (cheap, no re-encode).
  A supervisor thread keeps ffmpeg alive and, when `only_when_game_running`, runs
  it only while `cs2.exe` is open. `pick_encoder`/`pick_segments`/
  `build_capture_cmd` are **pure and unit-tested** (no screen/GPU needed).
  `ObsRecorder` is the optional legacy path (save replay buffer + watch dir).
  The engine rebuilds the recorder via `make_recorder` on `restart_recording`
  (after the wizard finishes or recording settings change).

- **Config is the integration seam.** [aegis/config.py](aegis/config.py) is a
  JSON store (`%APPDATA%\AegisClipper\config.json`) with dotted-path get/set,
  because the wizard and dashboard must *write* settings, not just read them. On
  first run it migrates a legacy `.env` and auto-detects OBS/CS2 paths. The
  engine, uploaders, and web layer all read from one `Config` instance.

- **Uploaders are a registry.** [aegis/uploaders/](aegis/uploaders/) — each target
  subclasses `Uploader` and **never raises** (returns `UploadResult(ok=False,...)`).
  `build_enabled(cfg)` returns the switched-on ones; both the engine's auto
  fan-out and the dashboard "Share" button use the same path. Adding a target =
  adding one module + a `REGISTRY` entry. Discord re-encodes oversized clips to
  fit 25 MB; YouTube's Google libs are optional and import-guarded; gallery is a
  no-op sink so "capture without sharing" is valid.

- **Catalog is the dashboard's source of truth.** [aegis/clips.py](aegis/clips.py)
  persists one `Clip` record per saved clip to `clips.json` (lock-guarded). Clip
  *video files* stay where OBS wrote them; the catalog only references them.

- **ffmpeg is isolated and optional.** [aegis/media.py](aegis/media.py) resolves
  the binary (config override → bundled next to the exe → PATH) and does
  thumbnails, the Discord size-fit re-encode, and montage concat. Every helper
  returns `None`/False instead of raising when ffmpeg is missing.

- **Entry + native window.** [aegis/app.py](aegis/app.py) runs the Flask server
  on a background thread, then presents the same web UI in a **native window**
  via pywebview (WebView2). A detached pystray icon runs alongside; the window's
  `closing` event hides it to the tray (engine keeps clipping) instead of
  quitting, and tray "Quit" exits. Degrades in order: pywebview window → tray +
  browser → headless. Every GUI lib (pywebview/pystray/Pillow) is import-guarded,
  so `--headless` and the engine never depend on them. The local HTTP server is
  *not* optional — CS2 GSI and the Discord webhook POST to it.

## Runtime dependencies (not controlled by the app)

- **ffmpeg** — now *core*, not optional: the built-in recorder, thumbnails, and
  montages all use it. Bundled into the build via `build.ps1 -Ffmpeg`; falls back
  to PATH. Without it, the built-in recorder can't capture.
- **CS2** launched after the GSI `.cfg` is copied into `csgo\cfg\` (the wizard's
  "Install GSI config" does this and rewrites the `uri` to the configured port).
- **WebView2 runtime** for the native window (preinstalled on Win11; the
  installer ships the bootstrapper for Win10).
- **OBS** — only when `recording.backend == "obs"` (optional advanced mode):
  Replay Buffer started + WebSocket server enabled.
- Telegram/Discord/YouTube credentials only if those targets are enabled.

## Build & CI

- **GitHub Actions** ([.github/workflows/release.yml](.github/workflows/release.yml))
  builds on `windows-latest` on tag push (`v*`): installs CPython, runs
  `build.ps1 -Ffmpeg -Installer -Portable`, and attaches `AegisClipper-Setup.exe`
  + `AegisClipper-portable.zip` to the Release. No local toolchain needed.
- **PyInstaller** ([packaging/aegis.spec](packaging/aegis.spec)) bundles ffmpeg
  (from `packaging/vendor/`), pywebview's runtime JS, and pythonnet (clr) for the
  EdgeChromium backend. **Building/running the frozen app needs standard CPython**
  — the repo's MSYS2 Python has no binary wheels for the GUI libs, so validate
  GUI/recorder behavior via CI or a python.org install, not the MSYS2 interpreter.

## Releases & auto-update

- **Version is single-sourced** in `aegis/__init__.py` (`__version__`). `build.ps1`
  reads it and passes `/DAppVersion` to Inno; the update checker compares releases
  against it. Bump it in one place per release.
- **Distribution = GitHub Releases** with `AegisClipper-Setup.exe`. Set
  `update.repo` (config default in `config.py`) to the `owner/repo` slug.
- **[aegis/update.py](aegis/update.py)** queries the Releases API, compares semver,
  and on apply downloads the setup asset and runs it `/SILENT` then `os._exit`s so
  files unlock. Source/non-frozen builds open the release page instead. Surfaced
  via `/api/update/check|apply` and a dashboard banner.
- **Upgrades never touch user state**: it all lives in `%APPDATA%` (paths.py), the
  Inno `AppId` is stable (in-place upgrade), and `_deep_merge(DEFAULTS, saved)`
  folds in new settings — so `first_run` stays false and the wizard never returns.

## Conventions

- New settings: add to `DEFAULTS` in `config.py` (deep-merged on load, so old
  config files stay valid) and surface them in the wizard form in `pages.py`.
- All persistent state lives under `aegis/paths.py` helpers — never write next to
  the program files (the installed copy is read-only).
- Log via `aegis/log.py`'s `log()` — it feeds the dashboard's `/api/logs` ring
  buffer, not just stdout.
