"""Flask app: GSI endpoint + dashboard + setup wizard + JSON API.

One server on the GSI port does double duty. CS2 POSTs ticks to ``/`` (method
POST); a browser hitting ``/`` (method GET) gets the dashboard — so the existing
GSI .cfg needs no change. Everything the web UI needs is a small JSON API under
``/api`` plus media-streaming routes for clip playback and thumbnails.

The HTML pages live in ``pages.py`` as self-contained strings (inline CSS/JS) so
there are no template/static files to locate after PyInstaller freezes the app.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_file

from . import __version__, config, paths
from .config import Config
from .clips import Catalog
from .engine import Engine, format_caption
from .log import log, recent
from .pages import DASHBOARD_HTML, SETUP_HTML


def create_app(cfg: Config, catalog: Catalog, engine: Engine) -> Flask:
    app = Flask(__name__)

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
        return DASHBOARD_HTML

    @app.get("/setup")
    def setup():
        return SETUP_HTML

    # ───────── status / logs ─────────
    @app.get("/api/status")
    def api_status():
        return jsonify(engine.status())

    @app.get("/api/logs")
    def api_logs():
        return jsonify(lines=recent(200))

    # ───────── clips ─────────
    @app.get("/api/clips")
    def api_clips():
        return jsonify(clips=[_clip_json(c) for c in catalog.list()])

    @app.post("/api/clips/<clip_id>")
    def api_update_clip(clip_id: str):
        body = request.get_json(silent=True) or {}
        allowed = {k: body[k] for k in ("title", "tags", "favorite") if k in body}
        c = catalog.update(clip_id, **allowed)
        return (jsonify(_clip_json(c)) if c else (jsonify(error="not found"), 404))

    @app.delete("/api/clips/<clip_id>")
    def api_delete_clip(clip_id: str):
        delete_file = request.args.get("file") == "1"
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
        return send_file(c.path, conditional=True)

    @app.get("/clip/<clip_id>/thumb")
    def clip_thumb(clip_id: str):
        c = catalog.get(clip_id)
        if c and c.thumb:
            tp = paths.thumbs_dir() / c.thumb
            if tp.exists():
                return send_file(tp, conditional=True)
        return _placeholder_thumb()

    # ───────── montage ─────────
    @app.post("/api/montage")
    def api_montage():
        ids = (request.get_json(silent=True) or {}).get("clip_ids", [])
        out = engine.build_montage(ids)
        if out is None:
            return jsonify(error="montage failed (need ffmpeg + valid clips)"), 400
        return jsonify(ok=True, file=out.name)

    @app.get("/api/montages")
    def api_montages():
        items = sorted(paths.montages_dir().glob("*.mp4"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonify(montages=[m.name for m in items])

    @app.get("/montage/<name>")
    def montage_video(name: str):
        p = paths.montages_dir() / Path(name).name
        return send_file(p, conditional=True) if p.exists() else ("not found", 404)

    # ───────── setup wizard API ─────────
    @app.get("/api/config")
    def api_get_config():
        return jsonify(cfg.as_dict())

    @app.post("/api/config")
    def api_set_config():
        patch = request.get_json(silent=True) or {}
        cfg.update(patch)
        cfg.save()
        return jsonify(ok=True, config=cfg.as_dict())

    @app.get("/api/detect")
    def api_detect():
        obs = config.detect_obs_replay_dir()
        cs2 = config.detect_cs2_cfg_dir()
        from . import media
        return jsonify(
            obs_replay_dir=str(obs) if obs else "",
            cs2_cfg_dir=str(cs2) if cs2 else "",
            ffmpeg=media.resolve_ffmpeg(cfg.get("ffmpeg_path", "")) or "",
            obs_connected=engine.obs.connected(),
        )

    @app.post("/api/install-gsi")
    def api_install_gsi():
        """Copy the GSI .cfg into CS2's cfg folder so detection 'just works'."""
        target_dir = (request.get_json(silent=True) or {}).get("cs2_cfg_dir", "")
        dest_dir = Path(target_dir) if target_dir else config.detect_cs2_cfg_dir()
        if not dest_dir or not dest_dir.is_dir():
            return jsonify(error="CS2 cfg folder not found — set it manually"), 400
        src = Path(__file__).resolve().parent.parent / "cfg" / "gamestate_integration_aegis_clipper.cfg"
        try:
            written = _write_gsi_cfg(src, dest_dir, int(cfg.get("engine.gsi_port")))
        except Exception as e:
            return jsonify(error=str(e)), 500
        log(f"Installed GSI config to {written}")
        return jsonify(ok=True, path=str(written))

    @app.post("/api/finish-setup")
    def api_finish_setup():
        cfg.set("first_run", False)
        cfg.save()
        return jsonify(ok=True)

    # ───────── auto-update ─────────
    @app.get("/api/update/check")
    def api_update_check():
        from . import update
        info = update.check(cfg)
        return jsonify(update=info.as_dict() if info else None, current=_version())

    @app.post("/api/update/apply")
    def api_update_apply():
        from . import update
        info = update.check(cfg)
        if not info:
            return jsonify(ok=False, detail="already up to date"), 400
        return jsonify(update.apply(info))

    return app


# ───────── helpers ─────────
def _version() -> str:
    return __version__


def _clip_json(c) -> dict:
    return {
        "id": c.id, "title": c.title, "kills": c.kills, "map": c.map_name,
        "round": c.round_n, "side": c.side, "tags": c.tags, "favorite": c.favorite,
        "size_mb": c.size_mb, "duration": c.duration, "created": c.created,
        "uploads": c.uploads, "missing": not c.exists(),
    }


def _write_gsi_cfg(src: Path, dest_dir: Path, port: int) -> Path:
    """Copy the template cfg, rewriting its uri to the configured GSI port."""
    dest = dest_dir / "gamestate_integration_aegis_clipper.cfg"
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
