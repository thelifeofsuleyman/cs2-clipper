"""Process entry: wire config + engine + web server, present a desktop window.

Layout at runtime:
  - Flask (engine GSI + dashboard) runs on a background thread on the GSI port.
    This server is mandatory: CS2 GSI and the Discord webhook both POST to it.
  - The UI is the same web dashboard, shown in a native window via pywebview
    (WebView2 on Windows) — so it looks like a real app, not a browser tab.
  - A tray icon runs alongside; closing the window hides it to the tray (the
    engine keeps clipping while you play). Tray "Quit" exits for real.

Graceful degradation, in order of preference:
  pywebview window (+ tray)  ->  tray icon + browser  ->  headless console.
Each layer is import-guarded, so a missing GUI lib never stops the engine.

Flags:
  --headless / --no-tray   no window/tray (plain console; CI, servers)
  --port N                 override the GSI/dashboard port for this run
"""
from __future__ import annotations

import sys
import threading
import webbrowser

from . import APP_NAME, config, paths
from .clips import Catalog
from .engine import Engine
from .log import log
from .web import create_app

WINDOW_W, WINDOW_H = 1180, 820


def _serve(app, port: int) -> None:
    # Prefer waitress (a real WSGI server) if present; fall back to Flask's.
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=port, threads=8, _quiet=True)
    except ImportError:
        app.run(host="127.0.0.1", port=port, threaded=True, debug=False)


def _banner(cfg: config.Config, port: int) -> None:
    backend = cfg.get("recording.backend", "builtin")
    rec = (f"OBS ({cfg.get('obs.replay_dir') or 'replay dir NOT SET'})"
           if backend == "obs"
           else f"built-in ({cfg.get('recording.preset')}, {cfg.get('recording.clip_seconds')}s clips)")
    log("=" * 60)
    log(f"{APP_NAME} v2  -  dashboard at http://127.0.0.1:{port}")
    log(f"  recording:   {rec}")
    log(f"  debounce:    {cfg.get('engine.debounce_sec')}s  min kills: {cfg.get('engine.min_kills')}")
    targets = [n for n in ('gallery', 'telegram', 'discord', 'youtube')
               if cfg.get(f'uploads.{n}.enabled')]
    log(f"  targets:     {', '.join(targets) or 'gallery only'}")
    log("=" * 60)


# ───────── tray icon (shared by the window and browser paths) ─────────
def _tray_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (64, 64), "#0d1017")
    ImageDraw.Draw(img).ellipse((16, 16, 48, 48), fill="#ff5a3c")
    return img


def _clips_folder(cfg) -> str:
    """Where saved clips land — built-in recorder dir, or OBS's replay dir."""
    if cfg.get("recording.backend") == "obs" and cfg.get("obs.replay_dir"):
        return cfg.get("obs.replay_dir")
    return str(paths.clips_dir())


def _open_folder(p) -> None:
    if not p:
        return
    try:
        import os
        os.startfile(str(p))  # type: ignore[attr-defined]  # Windows only
    except Exception as e:
        log(f"Could not open folder: {e}")


# ───────── UI: native window with close-to-tray ─────────
def _run_window(cfg, port: int, landing: str) -> bool:
    """Show the dashboard in a native window. Returns False if pywebview is
    unavailable so the caller can fall back to the browser+tray path."""
    try:
        import webview
    except ImportError:
        return False

    url = f"http://127.0.0.1:{port}{landing}"
    window = webview.create_window(
        APP_NAME, url, width=WINDOW_W, height=WINDOW_H, min_size=(900, 600),
    )

    tray = _start_tray_for_window(window, cfg, port)

    # Closing the window hides it to the tray instead of quitting, so the engine
    # keeps clipping during a match. If there's no tray, let the close go through.
    def _on_closing():
        if tray is None:
            return True
        try:
            window.hide()
        except Exception:
            return True
        log("Window hidden to tray — still clipping. Use the tray to reopen or quit.")
        return False  # cancel the close

    try:
        window.events.closing += _on_closing
    except Exception:
        pass  # older pywebview: window simply closes (engine stops) — acceptable

    webview.start()  # blocks the main thread until the app really exits
    return True


def _start_tray_for_window(window, cfg, port: int):
    """Detached tray icon that can reopen or quit the window. None if unavailable."""
    try:
        import pystray
    except ImportError:
        return None

    def _show(icon, item):
        try:
            window.show()
        except Exception as e:
            log(f"Could not show window: {e}")

    def _quit(icon, item):
        icon.stop()
        try:
            window.destroy()
        except Exception:
            import os
            os._exit(0)

    icon = pystray.Icon(
        "aegis", _tray_image(), APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Open Aegis Clipper", _show, default=True),
            pystray.MenuItem("Open clips folder",
                             lambda i, it: _open_folder(_clips_folder(cfg))),
            pystray.MenuItem("Quit", _quit),
        ),
    )
    icon.run_detached()
    return icon


# ───────── UI fallback: tray icon + system browser ─────────
def _run_tray_browser(cfg, port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    try:
        import pystray
    except ImportError:
        log("No GUI libs (pywebview/pystray) — running headless. Ctrl+C to stop.")
        threading.Event().wait()
        return

    icon = pystray.Icon(
        "aegis", _tray_image(), APP_NAME,
        menu=pystray.Menu(
            pystray.MenuItem("Open dashboard", lambda i, it: webbrowser.open(url), default=True),
            pystray.MenuItem("Open clips folder",
                             lambda i, it: _open_folder(_clips_folder(cfg))),
            pystray.MenuItem("Quit", lambda i, it: i.stop()),
        ),
    )
    icon.run()


def _existing_instance(port: int) -> bool:
    """True if our app is already serving on this port (single-instance check)."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
            return bool(json.loads(r.read().decode()).get("ok"))
    except Exception:
        return False


def _startup_cleanup() -> None:
    """Reclaim disk that a crash or interrupted update can leave behind:
    orphaned rolling-buffer segment dirs and the ~120 MB downloaded installer."""
    import shutil
    import tempfile
    from pathlib import Path
    try:
        for d in paths.buffer_dir().glob("rec_*"):
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass
    try:  # half-written capture temps from a crash mid-save
        for tmp in paths.clips_dir().glob(".raw_*.mp4"):
            tmp.unlink()
    except Exception:
        pass
    try:
        leftover = Path(tempfile.gettempdir()) / "AegisClipper-Setup.exe"
        if leftover.exists():
            leftover.unlink()
            log("Cleaned up a leftover update installer from %TEMP%")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    headless = "--headless" in argv or "--no-tray" in argv

    cfg = config.load()
    port = int(cfg.get("engine.gsi_port"))
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
        cfg.set("engine.gsi_port", port)

    # If an instance is already serving on this port, just open it and exit so a
    # double-launch doesn't crash trying to bind a busy port.
    if _existing_instance(port):
        log("Aegis Clipper is already running — opening the dashboard.")
        if not headless:
            webbrowser.open(f"http://127.0.0.1:{port}/")
        return 0

    # Reclaim disk left by previous crashes/updates BEFORE building the recorder
    # (which creates a fresh buffer dir of its own).
    _startup_cleanup()

    catalog = Catalog()
    engine = Engine(cfg, catalog)
    app = create_app(cfg, catalog, engine)

    _banner(cfg, port)
    threading.Thread(target=_serve, args=(app, port), daemon=True).start()

    # Start the recording backend unless the user is still in the setup wizard
    # (no point capturing until they've chosen quality/backend). The built-in
    # recorder self-gates on the game running, so this is cheap to leave on.
    if not cfg.get("first_run"):
        engine.start_recording()

    landing = "/setup" if cfg.get("first_run") else "/"

    if headless:
        log("Headless mode. Press Ctrl+C to stop.")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        engine.stop_recording()
        return 0

    # Prefer a native window; fall back to tray + browser if pywebview is absent.
    if not _run_window(cfg, port, landing):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}{landing}")).start()
        _run_tray_browser(cfg, port)
    engine.stop_recording()
    return 0


if __name__ == "__main__":
    sys.exit(main())
