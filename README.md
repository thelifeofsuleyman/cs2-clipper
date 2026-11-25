# Aegis Clipper

Automatic CS2 highlights for Windows. Aegis detects kills, saves replays to your
PC, and puts them in a desktop clip library.

[![Release downloads](https://img.shields.io/github/downloads/thelifeofsuleyman/cs2-clipper/total)](https://github.com/thelifeofsuleyman/cs2-clipper/releases)

**[Download the Windows installer](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest/download/AegisClipper-Setup.exe)** ·
[Portable ZIP](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest/download/AegisClipper-portable.zip) ·
[Release notes](https://github.com/thelifeofsuleyman/cs2-clipper/releases/latest)

The installer adds a Start menu shortcut and offers to launch Aegis when
Windows starts. To use the portable build, extract the ZIP and run `AegisClipper.exe`.

## Record your first highlight

1. Open Aegis Clipper and select **Save and open library**. Setup searches your
   Steam libraries and installs the CS2 integration when it finds the game.
2. Open CS2, or restart it if it was already running. The dashboard shows
   **CS2 connected** and **Replay buffer ready** when both are active.
3. Get a kill in a practice match. The clip appears in your library after
   your streak ends. Use **Save replay** anytime the buffer is ready.

Choose **Run in background** when closing the window to keep clipping. The
tray icon reopens the library.

## What you can do

- Browse, search, rename, and favorite clips in the desktop library.
- Share to Telegram, Discord, or YouTube after connecting a destination in Settings.
- In **Settings → Recording**, **Prioritize game FPS** limits built-in capture
  to 30 fps and uses direct GPU capture at desktop resolution when available.
  Turn it off to use a fixed quality preset or enable automatic clip effects.

Automatic highlights keep the moments around each kill and cut longer gaps
between them. **Save replay** saves a continuous window of the configured length.
Automatic highlights skip Deathmatch by default. Change the mode filter in
**Settings → Highlights**, or turn them off for manual replays only. Kills by
the person you are spectating don't trigger a clip. Set a global replay shortcut
under **Settings → Recording** to save a replay during a match.

Use **Settings → Storage** to pick the folder for new clips. Sort the library by
**Largest first** to find clips taking up space.

Open a video and choose **Trim clip** to set the start and end, preview the
selection, and save it as a separate video. The original stays in the library.
When capture is set to run only with CS2, Aegis keeps the last completed replay
segments available for 30 seconds after the game closes.

In **Share**, download the original or prepare a local MP4 copy for a 10 MB or
25 MB limit. Downloading a smaller copy keeps the original in your library.
In **Settings → Sharing**, turn off **Send automatic highlights** to keep
connected destinations available for manual sharing only.

**Compact recording** in Recording settings reduces bitrate for future built-in captures while keeping
their resolution and frame rate. The exact file size and detail depend on the scene.

To include audio with the built-in recorder, turn on **Capture speaker audio**
under **Settings → Recording**. This records sound from the default Windows
playback device, including other apps using it. To capture CS2 audio separately,
choose **OBS Studio** and configure an Application Audio Capture source, Replay
Buffer, and the WebSocket server in OBS.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Aegis can't find CS2 | Open **Settings → Counter-Strike 2**, expand **Use a custom CS2 installation**, and enter the game's `cfg` folder. Select **Connect CS2**. |
| Waiting for game updates | Check the CS2 integration in Settings, restart the game, and enter a match. |
| Capture unavailable | Run **Settings → Test screen capture** and check **Activity** for errors. With OBS, start its Replay Buffer. |
| Where are my saved clips? | Open **Open clips folder** from the tray menu. The built-in library stores clips under `%APPDATA%\AegisClipper\clips`. |

To report recording issues, use **Activity → Copy recorder diagnostics**. The
report includes the capture mode, FPS target, and replay save outcomes for the
current session. It stays local until you share it and contains no account
details or file paths.

Existing installs can use **Check for updates** in the dashboard. The installer
is currently unsigned, so Windows may display a publisher warning.

## Development

[Run from source, run the tests, and build a release](docs/development.md).
Licensed under the [MIT License](LICENSE).
