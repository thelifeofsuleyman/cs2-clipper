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

from . import APP_NAME, config
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
    log("=" * 60)
    log(f"{APP_NAME} v2  -  dashboard at http://127.0.0.1:{port}")
    log(f"  replay dir:  {cfg.get('obs.replay_dir') or 'NOT SET'}")
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

    tray = _start_tray_for_window(window, port)

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


def _start_tray_for_window(window, port: int):
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
                             lambda i, it: _open_folder(config.detect_obs_replay_dir())),
            pystray.MenuItem("Quit", _quit),
        ),
    )
    icon.run_detached()
    return icon


# ───────── UI fallback: tray icon + system browser ─────────
def _run_tray_browser(port: int) -> None:
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
                             lambda i, it: _open_folder(config.detect_obs_replay_dir())),
            pystray.MenuItem("Quit", lambda i, it: i.stop()),
        ),
    )
    icon.run()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    headless = "--headless" in argv or "--no-tray" in argv

    cfg = config.load()
    port = int(cfg.get("engine.gsi_port"))
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
        cfg.set("engine.gsi_port", port)

    catalog = Catalog()
    engine = Engine(cfg, catalog)
    app = create_app(cfg, catalog, engine)

    _banner(cfg, port)
    threading.Thread(target=_serve, args=(app, port), daemon=True).start()

    landing = "/setup" if cfg.get("first_run") else "/"

    if headless:
        log("Headless mode. Press Ctrl+C to stop.")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
        return 0

    # Prefer a native window; fall back to tray + browser if pywebview is absent.
    if not _run_window(cfg, port, landing):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}{landing}")).start()
        _run_tray_browser(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
