# Aegis Clipper

[![Build](https://github.com/thelifeofsuleyman/cs2-clipper/actions/workflows/release.yml/badge.svg)](https://github.com/thelifeofsuleyman/cs2-clipper/actions/workflows/release.yml)
[![Release](https://img.shields.io/github/v/release/thelifeofsuleyman/cs2-clipper?display_name=tag)](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/thelifeofsuleyman/cs2-clipper/total)](https://github.com/thelifeofsuleyman/cs2-clipper/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6)

**Aegis Clipper automatically saves CS2 highlights on your Windows PC.** The
built-in recorder keeps a rolling replay buffer and saves a clip when your kill
streak ends. Browse, play, and organize clips in the desktop app.

## Download for Windows

**[Download the Windows installer](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest/download/AegisClipper-Setup.exe)** ·
[Portable ZIP](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest/download/AegisClipper-portable.zip) ·
[Release notes](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest)

Choose the installer for a Start menu shortcut and in-app updates. For the
portable version, extract the full ZIP and run AegisClipper.exe from the
extracted folder.

## Record your first highlight

1. Open Aegis Clipper and select **Save and open library** in setup. Aegis looks
   through your Steam libraries and installs its CS2 integration when it finds
   the game.
2. Start CS2, or restart it if it was already open. The dashboard shows
   **Replay buffer ready** and **CS2 connected** once capture and game updates
   are active.
3. Get a kill in a practice match. When your streak ends, the clip appears in
   your library. Select **Save replay** to save the current buffer manually.

If setup can't find CS2, open **Settings → Counter-Strike 2**, expand
**Use a custom CS2 installation**, and select **Connect CS2** after entering
the game's cfg folder. For playback or recording issues, start with
**Settings → Test screen capture**, then check the [troubleshooting guide](#troubleshooting).

The built-in recorder uses the bundled FFmpeg and captures video. Use the
[optional OBS backend](#using-obs-instead-optional) to include game audio.

[Recording quality](#recording-quality) · [Troubleshooting](#troubleshooting) ·
[Run from source](#run-from-source-developers)

## Run from source (developers)

Needs Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m aegis            # full app: native window + tray (closes to tray)
python -m aegis --headless # no window/tray (console only) — same engine + dashboard
```

The UI is the dashboard / setup wizard, shown in a **native app window** (not a
browser tab) via WebView2, with a tray icon — closing the window hides it to the
tray so clipping continues while you play. Under the hood it's still served at
**http://127.0.0.1:3000** (the GSI listener and dashboard share one port).
`python clipper.py` still works as a launcher for old habits.

---

## Recording quality

Pick a preset in the wizard:

| Preset | Resolution / FPS | Best for |
|---|---|---|
| **Low-end** | 720p / 30 | weak CPUs/GPUs, integrated graphics |
| **Balanced** | 900p / 30 | most machines (default) |
| **High** | 1080p / 60 | gaming rigs |
| **Native** | source / 60 | best quality, strongest PCs |

Aegis tries supported hardware encoders and falls back to software or an alternate
desktop capture method if FFmpeg cannot start. By default it keeps a rolling
buffer while CS2 is running. The built-in recorder captures video. To include
game audio, configure audio sources and Replay Buffer in OBS.

### Using OBS instead (optional)

Prefer OBS's capture quality? In the wizard, expand **Use OBS instead** and enable
it. Then in OBS: enable the **Replay Buffer** (Settings → Output → Advanced) and
the **WebSocket server** (Tools → WebSocket Server Settings, port 4455). Aegis
will trigger OBS to save instead of using its own recorder.

---

## Features

| | |
|---|---|
| **Built-in recorder** | Own rolling replay buffer via ffmpeg — no OBS. GPU encode when available, light SW fallback. |
| **Auto-capture** | Kill-streak detection via CS2 GSI, debounced into one clip per streak. |
| **Web dashboard** | Browse, play, rename, tag, favorite, delete, and re-share clips. |
| **Multiple targets** | Local gallery (always), Telegram, Discord webhook, YouTube. |
| **Discord auto-fit** | Clips over Discord's 25 MB limit are transparently re-encoded to fit. |
| **Montage builder** | Select clips → one stitched video, optional music + 9:16 mobile export. |
| **Setup wizard** | System check, one-click CS2 integration, quality presets, link upload targets. |
| **Game integration** | Reads Valve's Game State Integration updates over localhost. |

### Upload targets at a glance

- **Local gallery** — always on; clips stay on your disk and in the dashboard.
- **Telegram** — create a bot via `@BotFather`, add it to a channel as admin,
  paste the token + channel ID. 2 GB file limit, no re-encode needed.
- **Discord** — paste a channel **webhook URL** (Server → Integrations →
  Webhooks). 25 MB cap; bigger clips auto-shrink.
- **YouTube** *(advanced)* — needs a Google Cloud OAuth "Desktop app"
  credential (`client_secrets.json`); first upload opens a browser to authorize.
  Install the optional libs: `pip install google-api-python-client google-auth-oauthlib`.

---

## Building & releasing

### The easy way — GitHub Actions (no local Python)

Pushing a version tag builds everything on GitHub's Windows runners and publishes
it to your repo's Releases automatically:

```bash
git tag v2.1.0
git push origin v2.1.0
```

The [release workflow](.github/workflows/release.yml) installs Python, bundles
ffmpeg, builds the app, compiles the installer, and attaches
**`AegisClipper-Setup.exe`** + **`AegisClipper-portable.zip`** to the Release. You
never need a build toolchain locally. (You can also trigger it from the Actions
tab via "Run workflow".)

### Building locally (optional)

From the repo root, with standard CPython on PATH:

```powershell
# App + bundled ffmpeg + installer + portable zip
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg -Installer -Portable
```

Outputs: `dist\AegisClipper\AegisClipper.exe`, `packaging\Output\AegisClipper-Setup.exe`,
and `packaging\Output\AegisClipper-portable.zip`. See [packaging/](packaging/).

### Cut a release

1. Bump `__version__` in [aegis/__init__.py](aegis/__init__.py) — the single
   source of truth (installer version + update checker read from it).
2. Set `update.repo` in the config defaults ([aegis/config.py](aegis/config.py))
   to your `owner/repo`.
3. Push a `v<version>` tag — GitHub Actions builds and publishes the Release.

**Distribute the installer to users; the portable zip is a fallback.** PyPI is
only for the `pip install` dev path.

**Users never redo setup on upgrade.** All settings and clips live in
`%APPDATA%\AegisClipper\`, the installer upgrades in place (stable `AppId`), and
config auto-merges new defaults — so the wizard never reappears.

**In-app auto-update:** on launch the app checks your GitHub Releases. If a newer
version exists, the dashboard shows an **Update now** banner that downloads the
new installer, runs it silently (Restart Manager closes + relaunches the app),
and applies the update in place. No manual download, no lost configuration.

---

## "Windows protected your PC" / antivirus warning

The installer isn't code-signed, so Windows SmartScreen shows **"unrecognized
app."** It's not malware — the source is all here — but a warning is expected for
any new, unsigned program. To install: click **More info → Run anyway**.

There is **no legitimate way to make this prompt disappear except code signing** —
that's the whole point of the check, and "tricks" to bypass it are what actual
malware does. The real options, in order of cost/effectiveness:

- **Azure Trusted Signing** (~$10/month, modern, needs identity verification) —
  the cheapest path to a signed exe.
- **EV code-signing certificate** (~$300–500/yr, hardware token) — gives
  **instant** SmartScreen trust, no warning from day one.
- **OV certificate** (~$100–300/yr) — signs the exe, but reputation still builds
  over downloads.
- **Do nothing** — reputation slowly improves as more people run it; users use
  "Run anyway."

What's already done for free: the exe carries proper **version metadata**
(publisher, product, version), which avoids the "Unknown publisher" line and
reduces antivirus false-positives common to PyInstaller builds. Signing is the
only thing that removes the prompt entirely.

## Disk usage & updates

Updates don't pile up: the downloaded installer is **deleted right after it
applies**, and on every launch the app **clears leftover installers and stale
recording-buffer files** from previous crashes. So repeated updates don't grow
your disk. (Each update still *downloads* ~120 MB — to cut that roughly in half,
drop the bundled `ffprobe`; see the size notes.) Your saved clips live in the
clips folder and are yours to keep or delete.

## Where things live

App state (settings, clip catalog, thumbnails, montages, logs) is stored under
`%APPDATA%\AegisClipper\`. Your actual clip video files stay wherever OBS writes
them. Set `AEGIS_DATA_DIR` to relocate the state folder (handy for dev).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Waiting for game updates | In Settings, check the Counter-Strike 2 integration. Connect CS2 if needed, then restart the game and enter a match. |
| Capture unavailable | Try **Test screen capture** in Settings and check Activity for the FFmpeg error. If using OBS, start its Replay Buffer. |
| "OBS WebSocket not reachable" | OBS → Tools → WebSocket Server Settings → Enable. Restart OBS. |
| "No new clip appeared" | The replay folder in Settings must match OBS's actual recording path. |
| Discord upload fails on big clips | ffmpeg isn't available to shrink them — bundle/install it, or use Telegram. |
| No thumbnails / montage greyed out | Install ffmpeg (see above). |
| GSI not detected | Re-run the wizard's "Install GSI config", then restart CS2. |
| Too many rounds in one clip | Lower the bundle window (try 5s) in Settings. |
| Solo kills feel spammy | Set min kills to 2 to only clip doubles and up. |

---

## How it works (architecture)

See [CLAUDE.md](CLAUDE.md) for the full module map. In short: a single Flask
process serves the CS2 GSI endpoint *and* the dashboard on one port; a debounce
timer turns kill bursts into one clip; the clip is cataloged and fanned out to
every enabled uploader; ffmpeg handles thumbnails and montages. Everything runs
locally.
