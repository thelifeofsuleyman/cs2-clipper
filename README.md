# Aegis Clipper

Automatic CS2 highlights for Windows. Aegis detects kills, saves replays to your
PC, and puts them in a desktop clip library.

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
- Select clips and build a montage.
- Share to Telegram, Discord, or YouTube after connecting a destination in Settings.
- Choose a recording preset in Settings. Start with **Balanced** (900p / 30 fps)
  or use **Low-end** (720p / 30 fps) to reduce recording load.

The built-in recorder captures video. To include game audio, enable **Use OBS
instead** in Aegis and configure audio sources, Replay Buffer, and the WebSocket
server in OBS.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Aegis can't find CS2 | Open **Settings → Counter-Strike 2**, expand **Use a custom CS2 installation**, and enter the game's `cfg` folder. Select **Connect CS2**. |
| Waiting for game updates | Check the CS2 integration in Settings, restart the game, and enter a match. |
| Capture unavailable | Run **Settings → Test screen capture** and check **Activity** for errors. With OBS, start its Replay Buffer. |
| Where are my saved clips? | Open **Open clips folder** from the tray menu. The built-in library stores clips under `%APPDATA%\AegisClipper\clips`. |

Existing installs can use **Check for updates** in the dashboard. The installer
is currently unsigned, so Windows may display a publisher warning.

## Development

[Run from source, run the tests, and build a release](docs/development.md).
Licensed under the [MIT License](LICENSE).
