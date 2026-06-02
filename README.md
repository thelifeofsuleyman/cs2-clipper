# Aegis Clipper

**Automatic CS2 highlight clipper — local-first, like allstar.gg but it all runs
on your PC.** Detects your kill streaks live, tells OBS to save the moment,
catalogs every clip in a built-in web dashboard, and (optionally) fans them out
to Telegram, Discord, or YouTube. Build montages from your best plays with one
click. No cloud account, no subscription, no screen-scraping — it reads CS2's
official Game State Integration, so it's anti-cheat safe.

```
CS2 kill streak ──► OBS Replay Buffer ──► local library + dashboard
                                          └─► Telegram / Discord / YouTube
                                          └─► one-click montage
```

**Smart bundling:** each kill resets a short timer; when you stop fragging, one
clip covering the *whole* streak is saved. Solo kill = one clip. Ace = one clip
with all five kills, not five files.

---

## Install (the easy way)

1. Download **AegisClipper-Setup.exe** from Releases and run it.
2. The app starts in your system tray and opens a **setup wizard** in your browser.
3. The wizard auto-detects OBS and CS2, installs the CS2 integration with one
   click, and lets you connect Telegram/Discord. Done.

That's it — play CS2 (with OBS's Replay Buffer running) and clips appear in the
dashboard automatically.

> **You still need [OBS Studio](https://obsproject.com/)** with the Replay Buffer
> enabled — that's what actually records. The wizard checks this for you. See
> [OBS setup](#obs-one-time) below.

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

## OBS (one-time)

**Replay Buffer** — Settings → Output → Output Mode **Advanced** → Replay Buffer
tab → Enable, Max Replay Time **45s**, Encoder **NVENC** (near-free on GPU).
Then click **Start Replay Buffer** each session (or auto-start it in
Settings → General).

**WebSocket** — Tools → WebSocket Server Settings → Enable. Default port 4455. If
you set a password, enter it in the wizard.

The setup wizard verifies both of these and reads your recording folder
automatically.

---

## Features

| | |
|---|---|
| **Auto-capture** | Kill-streak detection via CS2 GSI, debounced into one clip per streak. |
| **Web dashboard** | Browse, play, rename, tag, favorite, delete, and re-share clips. |
| **Multiple targets** | Local gallery (always), Telegram, Discord webhook, YouTube. |
| **Discord auto-fit** | Clips over Discord's 25 MB limit are transparently re-encoded to fit. |
| **Montage builder** | Select clips → one stitched video, optional music + 9:16 mobile export. |
| **Setup wizard** | Auto-detects OBS/CS2, installs the GSI config, links upload targets. |
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

## Building the installer

From the repo root, with Python on PATH:

```powershell
# App exe only
powershell -ExecutionPolicy Bypass -File packaging\build.ps1

# Also vendor ffmpeg (enables thumbnails + montage out of the box)
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg

# Also compile the one-click installer (needs Inno Setup 6 installed)
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Ffmpeg -Installer
```

Outputs: `dist\AegisClipper\AegisClipper.exe` and
`packaging\Output\AegisClipper-Setup.exe`. See [packaging/](packaging/) for the
PyInstaller spec and Inno Setup script.

> **ffmpeg** powers thumbnails and montages. Build with `-Ffmpeg` to bundle it,
> install it on PATH, or just point to it in the wizard. Without it, clipping +
> uploading still work — only thumbnails/montages are disabled.

## Releasing & updates

**Distribution:** ship via **GitHub Releases** — tag a version, attach
`AegisClipper-Setup.exe`, write notes. (PyPI is only for the `pip install` dev
path; the installer is the channel for users.)

**Cut a release:**

1. Bump `__version__` in [aegis/__init__.py](aegis/__init__.py) — the single
   source of truth (the installer and update checker read from it).
2. Set `update.repo` in the config defaults ([aegis/config.py](aegis/config.py))
   to your `owner/repo` so builds know where to check for updates.
3. `build.ps1 -Ffmpeg -Installer`, then create a GitHub Release tagged
   `v<version>` and upload `AegisClipper-Setup.exe`.

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
