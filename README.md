# Aegis Clipper

[![Build](https://github.com/thelifeofsuleyman/cs2-clipper/actions/workflows/release.yml/badge.svg)](https://github.com/thelifeofsuleyman/cs2-clipper/actions/workflows/release.yml)
[![Release](https://img.shields.io/github/v/release/thelifeofsuleyman/cs2-clipper?display_name=tag)](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/thelifeofsuleyman/cs2-clipper/total)](https://github.com/thelifeofsuleyman/cs2-clipper/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6)

**Automatic CS2 highlight clipper — local-first, like allstar.gg but it all runs
on your PC.** Detects your kill streaks live, records the moment with its own
**built-in lightweight recorder (no OBS needed)**, catalogs every clip in a
built-in web dashboard, and (optionally) fans them out to Telegram, Discord, or
YouTube. Build montages from your best plays with one click. No cloud account, no
subscription — kill detection reads CS2's official Game State Integration, so
it's anti-cheat safe.

```
CS2 kill streak ──► built-in recorder (rolling buffer) ──► local library + dashboard
   (GSI)            GPU encode if available, else light SW    └─► Telegram / Discord / YouTube
                                                              └─► one-click montage
```

**No OBS required.** Aegis keeps a short rolling replay buffer with bundled
ffmpeg, using your GPU encoder (NVENC/AMF/QSV) when present — near-zero cost
while you play — and a low-CPU software fallback on weak machines. It records
only while CS2 is open, so it's light. (Prefer OBS for max quality? It's still
supported as an optional backend.)

**Smart bundling:** each kill resets a short timer; when you stop fragging, one
clip covering the *whole* streak is saved. Solo kill = one clip. Ace = one clip
with all five kills, not five files.

---

## Install (the easy way)

1. Download **AegisClipper-Setup.exe** from Releases and run it.
2. The app opens as a desktop window with a quick **setup wizard**.
3. The wizard does a system check (recorder + GPU + CS2), installs the CS2
   integration with one click, lets you pick a quality preset, and connect
   Telegram/Discord. Done.

That's it — play CS2 and your highlights appear in the dashboard automatically.
**No OBS, no extra downloads** — the installer bundles everything (recorder,
WebView2 runtime, ffmpeg).

---

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

If a hardware encoder (NVENC/AMF/QSV) is present, encoding is offloaded to the
GPU for near-zero CPU cost. Otherwise a fast software encoder is used. Aegis only
records while CS2 is running, so it costs nothing when you're not playing.

### Using OBS instead (optional)

Prefer OBS's capture quality? In the wizard, expand **"Prefer OBS?"** and enable
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
| **Zero game impact** | Reads Valve's official GSI API — never touches game memory or files. |

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

## Where things live

App state (settings, clip catalog, thumbnails, montages, logs) is stored under
`%APPDATA%\AegisClipper\`. Your actual clip video files stay wherever OBS writes
them. Set `AEGIS_DATA_DIR` to relocate the state folder (handy for dev).

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| No clips appearing | Click **Start Replay Buffer** in OBS before the round. The wizard's status row tells you if it's off. |
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
