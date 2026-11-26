# Development

## Run from source

Use Python 3.10 or later on Windows. Install FFmpeg and FFprobe on `PATH` to use
the built-in recorder, thumbnails, and montage export from source.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest
.\.venv\Scripts\python.exe -m aegis
```

Use `python -m aegis --headless` to run the dashboard without a window or tray.
The dashboard and CS2 integration share `http://127.0.0.1:3000`. For isolated
development, set `AEGIS_DATA_DIR` to a test directory and pass `--port 3500`.
`python clipper.py` remains available for existing scripts.

Settings live in `%APPDATA%\AegisClipper\config.json` on Windows by default.
Existing `.env` settings are imported when the app first creates `config.json`.
Configure new installs through the setup screen.

To test CS2-only audio from source on Windows 11, build the helper with
`packaging\build-process-audio.cmd`. It uses Visual Studio C++ Build Tools and a
Windows 11 SDK, and writes the helper to `packaging/vendor/`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The unit tests use isolated app data and can run without CS2 or OBS. Montage
integration tests need FFmpeg on `PATH` or in `packaging/vendor/` on Windows.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`aegis/`](../aegis/) | Desktop app, clip library, recording, and local API |
| [`aegis/uploaders/`](../aegis/uploaders/) | Optional sharing destinations |
| [`cfg/`](../cfg/) | Template the setup screen installs in CS2 |
| [`packaging/`](../packaging/) | PyInstaller build and Inno Setup installer |
| [`tests/`](../tests/) | Unit tests and media integration tests |

CS2 sends Game State Integration updates to the local Flask server.
[`engine.py`](../aegis/engine.py) groups kills into streaks and asks the active
[recorder](../aegis/recorder.py) to save a replay. The
[clip catalog](../aegis/clips.py) feeds the dashboard, which pywebview displays
in a Windows app window.

## Build and publish

Update `__version__` in [`aegis/__init__.py`](../aegis/__init__.py) before tagging
a release. A pushed `v<version>` tag runs tests and builds the installer and
portable ZIP in the [release workflow](../.github/workflows/release.yml). Manual
workflow runs upload build artifacts to GitHub Actions.

For a local build, install Inno Setup and the C++ tools above, then run this
from the repository root.

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg -Installer -Portable
```

Build outputs go to `dist/` and `packaging/Output/`. For the optional YouTube
integration from source, install `google-api-python-client` and
`google-auth-oauthlib` in the virtual environment.

## Download and recording metrics

The README badge uses GitHub release asset download counts. For counts by
version and file, query the [public releases API](https://api.github.com/repos/thelifeofsuleyman/cs2-clipper/releases)
and read `assets[].download_count`. A download can be an update, a repeat
download, or a portable copy.

The app's **Copy recorder diagnostics** action exports local, per-session
recorder status and replay save counts. Users can paste that report into a
[recording issue](https://github.com/thelifeofsuleyman/cs2-clipper/issues/new?template=recording.yml).
**App health counts** in Activity is an opt-in local report with startup
durations, replay save outcomes, and FFmpeg's built-in recorder frame counters.
Capture frame counts start with the next recorder session after opting in.
The report can include public download counts for the latest release. The user
chooses when and where to share the copied report.

## CS2 demo benchmark

The Windows test replayed the same Nuke demo section from tick 3,850 for about
24 seconds per pass on a GeForce GTX 1650. Capture-on passes used direct D3D11,
NVENC, and desktop audio. Average FPS and 1% lows are estimates from CS2's
integer FPS histogram. The 1% low is the effective FPS of the slowest 1% of
frames. These short demo passes measure replay performance on one PC.

| Capture condition | Runs | Average FPS | 1% low FPS |
| --- | ---: | ---: | ---: |
| Capture off | 2 | 101.6–110.8 | 51.8–65.6 |
| Existing 30 FPS preset | 1 | 84.7 | 43.3 |
| 24 FPS trial | 2 | 80.5–92.2 | 34.9–42.3 |
| 18 FPS trial | 1 | 87.0 | 34.4 |

Reducing capture FPS had inconsistent results, so the default frame rates stay
as they were. The optional **Direct GPU only** preset limits capture to the
D3D11 hardware path. It reports an error when that path is unavailable.
