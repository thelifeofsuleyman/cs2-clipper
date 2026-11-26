# RoundLatch · CS2 clip recorder for Windows

RoundLatch records automatic Counter-Strike 2 highlights and manual replays
on Windows. Clips open in a local library where you can jump to kills, trim
footage, and prepare copies for sharing. The project previously shipped as
Aegis Clipper.

[![Release downloads](https://img.shields.io/github/downloads/thelifeofsuleyman/cs2-clipper/total)](https://github.com/thelifeofsuleyman/cs2-clipper/releases)

**[Download for Windows and view release notes](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest)**

The RoundLatch release includes `RoundLatch-Setup.exe` and a portable ZIP.
The installer adds a Start menu shortcut and can launch RoundLatch when Windows
starts. To use the portable build, extract the ZIP and run `RoundLatch.exe`.
Existing Aegis Clipper installations can upgrade in place and keep their
settings, clip catalog, and recordings.

## Record your first highlight

1. Open the app, select **Connect CS2** in the connection settings, and finish
   setup. The connection screen searches your Steam libraries for CS2.
2. Open CS2, or restart it if it was already running. The dashboard shows
   **CS2 connected** and **Replay buffer ready** when both are active.
3. Get a kill in a practice match. The clip appears in your library after
   your streak ends. Use **Save replay** anytime the buffer is ready.

The **Check your first replay** card helps you connect CS2, assign and test a
shortcut, and play back a clip to check its picture and sound. Open **Settings
→ Test recording** to run the check again.

Choose **Run in background** when closing the window to keep clipping. The
tray icon reopens the library.

## What you can do

- Browse, search, rename, and favorite clips in the desktop library.
- Share to Telegram, Discord, or YouTube after connecting a destination in Settings.
- In **Settings → Recording**, **Prioritize game FPS** limits built-in capture
  to 30 fps and uses direct GPU capture at desktop resolution when available.
  Turn it off to use a fixed quality preset or enable automatic clip effects.
  If capture uses the CPU, the dashboard shows a warning. **Low impact**
  captures at 540p and 24 fps and skips highlight effects.

Automatic highlights keep the moments around each kill and cut longer gaps
between them. **Save replay** saves a continuous window of the configured length.
Automatic highlights skip Deathmatch by default. Change the mode filter in
**Settings → Highlights**, or turn them off for manual replays only. Kills by
the person you are spectating don't trigger a clip. Set a global replay shortcut
under **Settings → Recording** to save a replay during a match. The tray and
dashboard confirm the save or show why it failed.

Use **Settings → Storage** to pick the folder for new clips. Sort the library by
**Largest first** to find clips taking up space. RoundLatch warns when the clip or
replay buffer drive has less than 2 GiB free.
Set a clip storage budget to limit new saves. Delete moves clips to **Recently
deleted**, where you can restore them or delete their videos to reclaim space.
Favorite clips are protected until you unfavorite them. In **Settings →
Storage**, use **Reconnect moved clips** to restore links to moved video files.

Open a video and click a kill marker to jump to the action. Choose **Trim clip**
to set the start and end around it, preview the selection, and save a separate
video. Open **Matches** to review and share clips by match, map, and round.
Markers and match recaps appear on new clips with CS2 game updates.
Under **Settings → Highlights**, choose Standard, Competitive, or Custom footage
around each kill. Built-in capture joins complete segments and can retain a
little extra footage at each cut.
When capture is set to run only with CS2, RoundLatch keeps the last completed replay
segments available for 30 seconds after the game closes.

In **Share**, download the original or prepare a local MP4 copy for a 10 MB or
25 MB limit. Downloading a smaller copy keeps the original in your library.
In the trim editor, preview the selection and its estimated size, then export
only that selection with **Share selection**. If CS2 is active, copies that
need encoding go to **Matches → After-match exports**.
In **Matches**, select up to 12 clips and queue exports with a limit per clip.
The queue prepares copies after the match and waits if a new match starts.
With CS2 open and game updates unavailable, queued exports wait for CS2 to close.
In **Settings → Sharing**, turn off **Send automatic highlights** to keep
connected destinations available for manual sharing only.

**Compact recording** in Recording settings reduces bitrate for future built-in captures while keeping
their resolution and frame rate. The exact file size and detail depend on the scene.
Choose **Direct GPU only** in **Settings → Recording → Advanced capture quality**
to use desktop-resolution capture through a compatible NVENC or AMF encoder
at up to 30 FPS. If direct capture is unavailable, the dashboard reports the error.

In **Settings → Recording**, select **CS2 only** to capture game audio on Windows
11. Choose **Desktop audio** to capture sounds from the default playback device.
If you use OBS Studio, choose audio sources in OBS.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| RoundLatch can't find CS2 | Open **Settings → Counter-Strike 2**, expand **Use a custom CS2 installation**, and enter the game's `cfg` folder. Select **Connect CS2**. |
| Waiting for game updates | Check the CS2 integration in Settings, restart the game, and enter a match. |
| Capture unavailable | Run **Settings → Test screen capture** and check **Activity** for errors. With OBS, start its Replay Buffer. |
| Where are my saved clips? | Open **Open clips folder** from the tray menu. The built-in library stores clips under `%APPDATA%\AegisClipper\clips`. |

To report recording issues, use **Activity → Copy recorder diagnostics**. The
report includes the capture mode, FPS target, and replay save outcomes for the
current session. It stays local until you share it and contains no account
details or file paths.

In **Activity → App health counts**, opt in to collect recorder start times,
clips saved, recording errors, and built-in capture frame counts on this PC.
The panel shows public release download counts from GitHub. You can copy a
local diagnostics report to share these counts.

## Check capture performance

Replay the same CS2 demo section with capture on and off to compare gameplay
FPS on your own PC. See the [benchmark method](docs/development.md#cs2-demo-benchmark).

Existing installs can use **Check for updates** in the dashboard. The installer
is currently unsigned, so Windows may display a publisher warning.

## Development

The [download and setup site](site/index.html) is static HTML, CSS, and JavaScript. To preview
it from the repository root on Windows, run:

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8765/`.

### Publish the website for free

1. Push the website changes to the public repository's `main` branch.
2. In [Settings → Pages](https://github.com/thelifeofsuleyman/cs2-clipper/settings/pages),
   set **Build and deployment → Source** to **GitHub Actions**.
3. In **Actions → Publish website**, choose **Run workflow** on `main`.
   When the deployment succeeds, open the link shown in the workflow or visit
   [the project site](https://thelifeofsuleyman.github.io/cs2-clipper/).

Changes to `site/` on `main` deploy automatically thereafter. GitHub Pages
serves the guide and calculator. Windows builds stay in GitHub Releases.

[Run from source, run the tests, and build a release](docs/development.md).
Licensed under the [MIT License](LICENSE).
