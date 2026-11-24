"""Flask app: GSI endpoint + dashboard + setup wizard + JSON API.

One server on the GSI port does double duty. CS2 POSTs ticks to ``/`` (method
POST); a browser hitting ``/`` (method GET) gets the dashboard — so the existing
GSI .cfg needs no change. Everything the web UI needs is a small JSON API under
``/api`` plus media-streaming routes for clip playback and thumbnails.

The HTML pages live in ``pages.py`` as self-contained strings (inline CSS/JS) so
there are no template/static files to locate after PyInstaller freezes the app.
"""
from __future__ import annotations

import re
import secrets
import threading
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, redirect, request, send_file

from . import __version__, config, paths
from .config import Config
from .clips import Catalog
from .engine import Engine, format_caption
from .log import log, recent
from .pages import DASHBOARD_HTML, SETUP_HTML


def create_app(cfg: Config, catalog: Catalog, engine: Engine) -> Flask:
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=256 * 1024, AEGIS_SESSION=secrets.token_hex(32))
    session = app.config["AEGIS_SESSION"]
    media_job = threading.Lock()

    @app.before_request
    def check_local_request():
        if not re.fullmatch(r"(?:localhost|127\.0\.0\.1)(?::[0-9]{1,5})?", request.host, re.I):
            abort(400)
        origin = request.headers.get("Origin")
        if origin is not None and origin != request.host_url.rstrip("/"):
            abort(403)
        if request.headers.get("Sec-Fetch-Site") in {"cross-site", "same-site"}:
            abort(403)
        if request.path.startswith("/api/"):
            if not secrets.compare_digest(request.headers.get("X-Aegis-Session", "").encode(), session.encode()):
                abort(403)

    @app.after_request
    def protect_response(response):
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/") or response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        if nonce := g.get("csp_nonce"):
            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; script-src 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
        return response

    def render_page(page: str) -> str:
        g.csp_nonce = secrets.token_hex(24)
        return page.replace("<script>", f'<script nonce="{g.csp_nonce}">').replace("%SESSION%", session)

    def run_media_job(run):
        if not media_job.acquire(blocking=False):
            return jsonify(ok=False, error="Another video operation is still running."), 409
        try:
            return run()
        except Exception as e:
            log(f"Video operation failed: {e}")
            return jsonify(ok=False, error="Video operation failed. See Activity for details."), 500
        finally:
            media_job.release()

    # ───────── GSI ingest (CS2 POSTs here) ─────────
    @app.post("/")
    def gsi_in():
        try:
            engine.handle_payload(request.get_json(silent=True) or {})
        except Exception as e:
            log(f"handle_payload error: {e}")
        return "", 200

    @app.get("/health")
    def health():
        return jsonify(ok=True, **engine.status())

    # ───────── pages ─────────
    @app.get("/")
    def dashboard():
        if cfg.get("first_run"):
            return redirect("/setup")
        return render_page(DASHBOARD_HTML.replace("%VER%", __version__)
                           .replace("%AUTO_UPDATE%", "true" if cfg.get("update.auto_check") else "false"))

    @app.get("/setup")
    def setup():
        return render_page(SETUP_HTML)

    # ───────── status / logs ─────────
    @app.get("/api/status")
    def api_status():
        return jsonify(engine.status())

    @app.get("/api/diagnostics")
    def api_diagnostics():
        status = engine.status()
        recorder_status = status["recorder"]
        return jsonify(
            version=__version__,
            capture={key: recorder_status[key] for key in ("backend", "state", "encoder", "method", "fps", "audio")
                     if key in recorder_status},
            buffer_ready=status["capturing"],
            game_updates_connected=status["gsi_connected"],
            prioritize_game_fps=bool(cfg.get("recording.prioritize_game_fps", True)),
            this_session=engine.replay_metrics(),
        )

    @app.post("/api/quit")
    def api_quit():
        """Fully exit the app (stop the engine + process). Used by the close
        dialog's 'Quit' choice; 'Run in background' just closes the window."""
        import os
        import threading

        def _bye():
            try:
                engine.stop_recording()
            except Exception:
                pass
            os._exit(0)
        threading.Timer(0.5, _bye).start()   # let the HTTP response return first
        return jsonify(ok=True)

    @app.get("/api/logs")
    def api_logs():
        return jsonify(lines=recent(200))

    # ───────── clips ─────────
    @app.get("/api/clips")
    def api_clips():
        return jsonify(clips=[_clip_json(c) for c in catalog.list()])

    @app.post("/api/clips/<clip_id>")
    def api_update_clip(clip_id: str):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Provide clip changes as a JSON object."), 400
        if "title" in body and (not isinstance(body["title"], str) or len(body["title"]) > 240):
            return jsonify(error="Clip titles can be up to 240 characters."), 400
        if "favorite" in body and not isinstance(body["favorite"], bool):
            return jsonify(error="Favorite must be true or false."), 400
        if "tags" in body and (not isinstance(body["tags"], list)
                               or not all(isinstance(tag, str) for tag in body["tags"])):
            return jsonify(error="Tags must be a list of text labels."), 400
        allowed = {k: body[k] for k in ("title", "tags", "favorite") if k in body}
        c = catalog.update(clip_id, **allowed)
        return (jsonify(_clip_json(c)) if c else (jsonify(error="not found"), 404))

    @app.delete("/api/clips/<clip_id>")
    def api_delete_clip(clip_id: str):
        # Delete the actual video file too, by default (pass ?keep=1 to keep it).
        delete_file = request.args.get("keep") != "1"
        ok = catalog.remove(clip_id, delete_file=delete_file)
        return (jsonify(ok=True) if ok else (jsonify(error="not found"), 404))

    @app.post("/api/clips/<clip_id>/share")
    def api_share_clip(clip_id: str):
        c = catalog.get(clip_id)
        if not c or not c.exists():
            return jsonify(error="clip file missing"), 404
        caption = c.title or format_caption(c.kills, c.map_name, c.round_n, c.side)
        return jsonify(results=engine.fan_out(c, caption))

    # ───────── media streaming (range-enabled for seeking) ─────────
    @app.get("/clip/<clip_id>/video")
    def clip_video(clip_id: str):
        c = catalog.get(clip_id)
        if not c or not c.exists():
            return "not found", 404
        path = Path(c.path)
        mime = {".mp4": "video/mp4", ".mkv": "video/x-matroska", ".mov": "video/quicktime"}
        if not path.is_file() or path.suffix.lower() not in mime:
            return "not found", 404
        return send_file(path, conditional=True, mimetype=mime[path.suffix.lower()])

    @app.get("/clip/<clip_id>/thumb")
    def clip_thumb(clip_id: str):
        c = catalog.get(clip_id)
        if c and c.thumb:
            root = paths.thumbs_dir().resolve()
            tp = (root / c.thumb).resolve()
            if tp.parent == root and tp.suffix.lower() == ".jpg" and tp.is_file():
                return send_file(tp, conditional=True, mimetype="image/jpeg")
        return _placeholder_thumb()

    # ───────── montage ─────────
    @app.post("/api/montage")
    def api_montage():
        body = request.get_json(silent=True)
        ids = body.get("clip_ids") if isinstance(body, dict) else None
        limit = int(cfg.get("montage.max_clips", 12))
        if not isinstance(ids, list) or not 1 <= len(ids) <= limit or not all(isinstance(i, str) for i in ids):
            return jsonify(error=f"Select between 1 and {limit} available clips."), 400

        def build():
            out = engine.build_montage(ids)
            if out is None:
                return jsonify(error="Could not build the montage. Check your clips and the Activity log."), 400
            return jsonify(ok=True, file=out.name)

        return run_media_job(build)

    @app.get("/api/montages")
    def api_montages():
        items = sorted(paths.montages_dir().glob("*.mp4"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonify(montages=[m.name for m in items])

    @app.get("/montage/<name>")
    def montage_video(name: str):
        root = paths.montages_dir().resolve()
        p = (root / name).resolve()
        if p.parent != root or p.suffix.lower() != ".mp4" or not p.is_file():
            return "not found", 404
        return send_file(p, conditional=True, mimetype="video/mp4")

    # ───────── setup wizard API ─────────
    @app.get("/api/config")
    def api_get_config():
        return jsonify(cfg.as_dict())

    @app.post("/api/config")
    def api_set_config():
        patch = request.get_json(silent=True)
        if not _valid_settings_patch(patch):
            return jsonify(error="Provide settings as a JSON object with settings groups."), 400
        before = cfg.as_dict()
        cfg.update(patch)
        cfg.save()
        recording = cfg.get("recording")
        backend_changed = before["recording"] != recording
        if recording["backend"] == "obs":
            backend_changed = backend_changed or before["obs"] != cfg.get("obs")
        # Editing sharing or highlight settings should not clear the replay buffer.
        if backend_changed and not cfg.get("first_run"):
            engine.restart_recording()
        return jsonify(ok=True, config=cfg.as_dict())

    @app.get("/api/detect")
    def api_detect():
        from . import media
        cs2 = _find_gsi_dir(cfg)
        ffmpeg = media.resolve_ffmpeg(cfg.get("ffmpeg_path", ""))
        # Report the running encoder, if any. Spawning FFmpeg to list compiled
        # encoders can hang first-run detection on a cold Windows launch.
        encoder = ""
        if cfg.get("recording.backend") == "builtin":
            status = engine.recorder.status()
            if status.get("capturing"):
                encoder = status.get("encoder", "")
        return jsonify(
            cs2_cfg_dir=str(cs2) if cs2 else "",
            gsi_installed=bool(cs2 and _gsi_is_current(cs2, int(cfg.get("engine.gsi_port")))),
            ffmpeg=ffmpeg or "",
            encoder=encoder,
            gpu_accel=bool(encoder and encoder != "libx264"),
            obs_replay_dir=str(config.detect_obs_replay_dir() or ""),
        )

    @app.post("/api/install-gsi")
    def api_install_gsi():
        """Copy the GSI .cfg into CS2's cfg folder so detection 'just works'."""
        body = request.get_json(silent=True)
        target_dir = body.get("cs2_cfg_dir", "") if isinstance(body, dict) else ""
        if not isinstance(target_dir, str):
            return jsonify(error="Enter a CS2 cfg folder path."), 400
        dest_dir = Path(target_dir) if target_dir else _find_gsi_dir(cfg)
        if not dest_dir or not dest_dir.is_dir():
            return jsonify(error="CS2 cfg folder not found — set it manually"), 400
        try:
            written, changed = install_gsi(cfg, dest_dir)
            if target_dir and str(dest_dir) != cfg.get("engine.cs2_cfg_dir"):
                cfg.set("engine.cs2_cfg_dir", str(dest_dir))
                cfg.save()
        except Exception as e:
            return jsonify(error=str(e)), 500
        return jsonify(ok=True, path=str(written), restart_required=changed)

    @app.post("/api/test-clip")
    def api_test_clip():
        return run_media_job(lambda: jsonify(engine.trigger_test_clip()))

    @app.post("/api/capture-test")
    def api_capture_test():
        return run_media_job(lambda: jsonify(engine.trigger_capture_test()))

    @app.post("/api/replay")
    def api_save_replay():
        return run_media_job(lambda: jsonify(engine.save_replay()))

    @app.post("/api/finish-setup")
    def api_finish_setup():
        if not cfg.get("first_run"):
            return jsonify(ok=True)
        dest = _find_gsi_dir(cfg)
        restart_required = False
        warning = ""
        if dest and not _gsi_is_current(dest, int(cfg.get("engine.gsi_port"))):
            try:
                _, restart_required = install_gsi(cfg, dest)
            except OSError as e:
                warning = f"Could not connect CS2: {e}"
                log(warning)
        cfg.set("first_run", False)
        cfg.save()
        engine.restart_recording()  # begin capturing now that setup is done
        return jsonify(ok=True, restart_required=restart_required, warning=warning)

    # ───────── auto-update ─────────
    @app.get("/api/update/check")
    def api_update_check():
        from . import update
        info = update.check(cfg)
        return jsonify(update=info.as_dict() if info else None,
                       current=_version(), error=update.get_last_error())

    @app.post("/api/update/apply")
    def api_update_apply():
        from . import update
        info = update.check(cfg)
        if not info:
            return jsonify(ok=False, detail="already up to date"), 400
        return jsonify(update.start_apply(info))

    @app.get("/api/update/progress")
    def api_update_progress():
        from . import update
        return jsonify(update.get_progress())

    return app


# ───────── helpers ─────────
_UI_SETTINGS = {
    "engine": {"debounce_sec", "min_kills", "cs2_cfg_dir"},
    "recording": {"backend", "preset", "prioritize_game_fps", "speaker_audio",
                  "clip_seconds", "only_when_game_running"},
    "polish": {"enabled"},
    "obs": {"replay_dir", "port", "password"},
    "uploads": {
        "telegram": {"enabled", "bot_token", "chat_id"},
        "discord": {"enabled", "webhook_url"},
        "youtube": {"enabled", "client_secrets", "privacy"},
    },
}


def _valid_settings_patch(patch, allowed=_UI_SETTINGS):
    if not isinstance(patch, dict) or any(key not in allowed for key in patch):
        return False
    if isinstance(allowed, set):
        return all(type(value) in (str, int, float, bool) for value in patch.values())
    return all(_valid_settings_patch(value, allowed[key]) for key, value in patch.items())


def _version() -> str:
    return __version__


def _clip_json(c) -> dict:
    return {
        "id": c.id, "title": c.title, "kills": c.kills, "map": c.map_name,
        "round": c.round_n, "side": c.side, "tags": c.tags, "favorite": c.favorite,
        "size_mb": c.size_mb, "duration": c.duration, "created": c.created,
        "uploads": c.uploads, "missing": not c.exists(),
    }


_GSI_FILENAME = "gamestate_integration_aegis_clipper.cfg"


def _find_gsi_dir(cfg: Config) -> Path | None:
    stored = cfg.get("engine.cs2_cfg_dir", "")
    if stored and Path(stored).is_dir():
        return Path(stored)
    return config.detect_cs2_cfg_dir()


def _gsi_is_current(directory: Path, port: int) -> bool:
    try:
        text = (directory / _GSI_FILENAME).read_text(encoding="utf-8")
        return f'"http://127.0.0.1:{port}"' in text
    except (OSError, UnicodeError):
        return False


def install_gsi(cfg: Config, directory: Path) -> tuple[Path, bool]:
    port = int(cfg.get("engine.gsi_port"))
    if _gsi_is_current(directory, port):
        return directory / _GSI_FILENAME, False
    src = Path(__file__).resolve().parent.parent / "cfg" / _GSI_FILENAME
    written = _write_gsi_cfg(src, directory, port)
    log(f"Installed CS2 integration to {written}")
    return written, True


def _write_gsi_cfg(src: Path, dest_dir: Path, port: int) -> Path:
    """Copy the template cfg, rewriting its uri to the configured GSI port."""
    dest = dest_dir / _GSI_FILENAME
    if src.exists():
        text = src.read_text(encoding="utf-8")
    else:
        text = _DEFAULT_GSI_CFG
    import re
    text = re.sub(r'"uri"\s+"[^"]*"', f'"uri"           "http://127.0.0.1:{port}"', text)
    dest.write_text(text, encoding="utf-8")
    return dest


_DEFAULT_GSI_CFG = '''"Aegis Clipper Service v1"
{
    "uri"           "http://127.0.0.1:3000"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.5"
    "heartbeat"     "10.0"
    "data"
    {
        "provider"            "1"
        "map"                 "1"
        "round"               "1"
        "player_id"           "1"
        "player_state"        "1"
        "player_match_stats"  "1"
    }
}
'''


# A 1x1 transparent-ish gray PNG used when a clip has no thumbnail yet.
def _placeholder_thumb() -> Response:
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return Response(png, mimetype="image/png")
