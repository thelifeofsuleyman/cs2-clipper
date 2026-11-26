from pathlib import Path


def _gsi(kills):
    return {"player": {"match_stats": {"kills": kills}, "team": "T"},
            "map": {"name": "de_mirage", "round": 3}}


def test_first_run_redirects_to_setup(app_client):
    client, cfg, *_ = app_client
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302 and "/setup" in r.headers["Location"]


def test_dashboard_after_setup(app_client):
    client, cfg, *_ = app_client
    cfg.set("first_run", False)
    r = client.get("/")
    assert r.status_code == 200 and b"clipGrid" in r.data


def test_setup_page_renders(app_client):
    client, *_ = app_client
    r = client.get("/setup")
    assert r.status_code == 200 and b"rec_preset" in r.data


def test_api_requires_same_origin_and_dashboard_session(app_client):
    client, _, _, _ = app_client
    bare = client.application.test_client()
    assert bare.get("/api/config").status_code == 403
    assert client.get("/api/config", headers={"Host": "example.test"}).status_code == 400
    assert client.post("/api/replay", headers={"Origin": "https://example.test"}).status_code == 403
    assert client.post("/", headers={"Sec-Fetch-Site": "cross-site"}, json=_gsi(0)).status_code == 403
    assert bare.post("/", json=_gsi(0)).status_code == 200
    assert "frame-ancestors 'none'" in bare.get("/setup").headers["Content-Security-Policy"]


def test_browser_settings_cannot_change_execution_paths(app_client):
    client, cfg, _, _ = app_client
    assert client.post("/api/config", json={"ffmpeg_path": "another.exe"}).status_code == 400
    assert client.post("/api/config", json={"update": {"repo": "other/project"}}).status_code == 400
    assert cfg.get("ffmpeg_path") == ""


def test_custom_folder_and_download_original(app_client, data_dir, monkeypatch):
    from aegis.clips import Clip

    client, cfg, catalog, engine = app_client
    destination = data_dir / "saved clips"
    assert client.post("/api/config", json={"storage": {"clips_dir": "relative"}}).status_code == 400
    response = client.post("/api/config", json={"storage": {"clips_dir": str(destination)}})
    assert response.status_code == 200 and cfg.get("storage.clips_dir") == str(destination)
    old_file = data_dir / "old.mp4"
    old_file.write_bytes(b"old video")
    catalog.add(Clip(id="old", path=str(old_file), created=1))

    def save(_seconds, path, _ranges):
        assert path.parent == destination
        path.write_bytes(b"new video")
        return path

    monkeypatch.setattr(engine.recorder, "save", save)
    result = client.post("/api/replay").get_json()
    assert result["ok"]
    old = client.get("/clip/old/download")
    assert old.headers["Content-Disposition"].startswith("attachment;")
    assert old.data == b"old video"
    assert client.get("/clip/" + result["clip_id"] + "/video").data == b"new video"


def test_share_copy_respects_size_limit_and_clears_scratch(app_client, data_dir, monkeypatch):
    from aegis import media
    from aegis.clips import Clip

    client, _, catalog, engine = app_client
    source = data_dir / "recording.mp4"
    source.write_bytes(b"original")
    catalog.add(Clip(id="video", path=str(source), created=1))
    url = "/api/clips/video/export"
    assert client.post(url, json={"max_mb": 0}).status_code == 400
    original = client.post(url, json={"max_mb": 10})
    assert original.headers["X-Aegis-Original"] == "1" and original.data == b"original"

    with source.open("r+b") as content:
        content.truncate(10_000_001)
    output_paths = []

    def encode(ffmpeg, video, out, max_bytes, *, pause):
        assert video == source and max_bytes == 10_000_000
        assert not pause()
        output_paths.append(out)
        out.write_bytes(b"fit video")
        return True

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "ffmpeg")
    monkeypatch.setattr(media, "reencode_to_fit", encode)
    monkeypatch.setattr(engine, "can_batch_export", lambda: True)
    exported = client.post(url, json={"max_mb": 10})
    assert exported.mimetype == "video/mp4" and exported.data == b"fit video"
    assert "recording-share.mp4" in exported.headers["Content-Disposition"]
    assert not output_paths[0].parent.exists()
    assert source.stat().st_size == 10_000_001
    assert client.get("/api/clips").get_json()["clips"][0]["size_bytes"] == 10_000_001


def test_trimming_creates_a_new_local_clip(app_client, data_dir, monkeypatch):
    from aegis import media
    from aegis.clips import Clip

    client, cfg, catalog, _ = app_client
    folder = data_dir / "chosen folder"
    cfg.set("storage.clips_dir", str(folder))
    source = data_dir / "existing.mp4"
    source.write_bytes(b"original")
    original = Clip(id="original", path=str(source), created=1, kills=4, title="Mirage", tags=["test"])
    catalog.add(original)
    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "ffmpeg")
    monkeypatch.setattr(media, "make_thumbnail", lambda *args: None)
    monkeypatch.setattr(media, "probe_duration", lambda _, file: 10 if file == source else 3.25)

    def trim(_ffmpeg, video, out, start, end):
        assert video == source and (start, end) == (1.25, 4.5)
        out.write_bytes(b"trimmed")
        return True

    monkeypatch.setattr(media, "trim_clip", trim)
    url = "/api/clips/original/trim"
    assert client.post(url, json={"start": -1, "end": 3}).status_code == 400
    assert client.post(url, json={"start": 9, "end": 12}).status_code == 400
    response = client.post(url, json={"start": 1.25, "end": 4.5})
    assert response.status_code == 201
    edited = response.get_json()["clip"]
    assert edited["id"] != original.id and edited["title"] == "Mirage (trim)"
    assert edited["kills"] == 0 and edited["tags"] == ["test", "trimmed"]
    assert edited["uploads"] == {}
    assert Path(catalog.get(edited["id"]).path).parent == folder
    assert client.get("/clip/" + edited["id"] + "/video").data == b"trimmed"
    assert source.read_bytes() == b"original"


def test_config_restarts_only_the_active_recorder(app_client, monkeypatch):
    client, cfg, _, engine = app_client
    cfg.set("first_run", False)
    restarts = []
    monkeypatch.setattr(engine, "restart_recording", lambda: restarts.append(cfg.get("recording.backend")))

    client.post("/api/config", json={"obs": {"port": 4456}})
    assert restarts == []
    client.post("/api/config", json={"recording": {"backend": "obs"}})
    client.post("/api/config", json={"obs": {"port": 4457}})
    client.post("/api/config", json={"engine": {"min_kills": 2}})
    assert restarts == ["obs", "obs"]


def test_quit_endpoint_schedules_exit(app_client, monkeypatch):
    client, *_ = app_client
    scheduled = {}

    class FakeTimer:
        def __init__(self, t, fn):
            self.fn = fn
        def start(self):
            scheduled["yes"] = True   # don't actually fire -> no os._exit in tests

    monkeypatch.setattr("threading.Timer", FakeTimer)
    r = client.post("/api/quit").get_json()
    assert r["ok"] is True and scheduled.get("yes")


def test_health_and_status(app_client):
    client, *_ = app_client
    h = client.get("/health").get_json()
    assert h["ok"] is True and "recorder" in h
    s = client.get("/api/status").get_json()
    assert "capturing" in s and "enabled_targets" in s


def test_diagnostics_only_reports_allowlisted_session_metrics(app_client, monkeypatch):
    client, _, _, engine = app_client
    monkeypatch.setattr(engine.recorder, "status", lambda: {
        "backend": "builtin", "capturing": True, "encoder": "h264_nvenc",
        "method": "ddagrab-d3d11", "fps": 30, "detail": "private local path",
    })
    report = client.get("/api/diagnostics").get_json()
    assert report["capture"] == {"backend": "builtin", "encoder": "h264_nvenc",
                                 "method": "ddagrab-d3d11", "fps": 30}
    assert report["this_session"] == {"attempts": 0, "saved": 0, "last_save_ms": None}
    assert "private local path" not in str(report)


def test_config_get_and_post_roundtrip(app_client):
    client, cfg, *_ = app_client
    r = client.post("/api/config", json={"recording": {"preset": "low", "clip_seconds": 20}})
    rc = r.get_json()["config"]["recording"]
    assert rc["preset"] == "low" and rc["clip_seconds"] == 20
    assert client.get("/api/config").get_json()["recording"]["preset"] == "low"


def test_detect_endpoint_shape(app_client, monkeypatch):
    from aegis import media, recorder

    def unexpected_probe(_):
        raise AssertionError("Settings detection must not start an FFmpeg process")

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "ffmpeg.exe")
    monkeypatch.setattr(recorder, "_encoders_text", unexpected_probe)
    client, *_ = app_client
    response = client.get("/api/detect")
    assert response.status_code == 200
    d = response.get_json()
    for key in ("cs2_cfg_dir", "ffmpeg", "encoder", "gpu_accel"):
        assert key in d


def test_gsi_ingest_updates_pending(app_client):
    client, cfg, catalog, engine = app_client
    cfg.set("engine.debounce_sec", 999)        # don't fire during the test
    client.post("/", json=_gsi(0))
    client.post("/", json=_gsi(2))
    assert engine.status()["pending_kills"] == 2


def test_clips_listing_empty(app_client):
    client, *_ = app_client
    assert client.get("/api/clips").get_json() == {"clips": []}


def test_delete_clip_removes_the_file(app_client, data_dir):
    import time
    from aegis import paths
    from aegis.clips import Clip
    client, cfg, catalog, engine = app_client
    f = paths.clips_dir() / "mirage_4K.mp4"
    f.write_bytes(b"x" * 16)
    catalog.add(Clip(id="c1", path=str(f), created=time.time(), kills=4))
    assert client.delete("/api/clips/c1").get_json()["ok"] is True
    assert not f.exists()                       # file actually deleted, not just unlisted


def test_delete_clip_keep_file(app_client, data_dir):
    import time
    from aegis import paths
    from aegis.clips import Clip
    client, cfg, catalog, engine = app_client
    f = paths.clips_dir() / "dust2_1K.mp4"
    f.write_bytes(b"x" * 16)
    catalog.add(Clip(id="c2", path=str(f), created=time.time(), kills=1))
    client.delete("/api/clips/c2?keep=1")
    assert f.exists()                           # ?keep=1 leaves the file


def test_finish_setup_flips_first_run(app_client):
    client, cfg, *_ = app_client
    assert cfg.get("first_run") is True
    client.post("/api/finish-setup")
    assert cfg.get("first_run") is False


def test_finish_setup_installs_detected_cs2_integration_once(app_client, monkeypatch, tmp_path):
    from aegis import web

    client, cfg, _, engine = app_client
    cfg.set("engine.gsi_port", 3501)
    monkeypatch.setattr(web.config, "detect_cs2_cfg_dir", lambda: tmp_path)
    starts = []
    monkeypatch.setattr(engine, "restart_recording", lambda: starts.append(True))
    first = client.post("/api/finish-setup").get_json()
    second = client.post("/api/finish-setup").get_json()
    installed = tmp_path / web._GSI_FILENAME
    assert first["restart_required"] and second["ok"]
    assert '"http://127.0.0.1:3501"' in installed.read_text(encoding="utf-8")
    assert client.get("/api/detect").get_json()["gsi_installed"]
    assert starts == [True]


def test_update_check_endpoint(app_client):
    client, cfg, *_ = app_client
    cfg.set("update.repo", "OWNER/REPO")        # placeholder -> no network, no update
    j = client.get("/api/update/check").get_json()
    assert j["update"] is None and "current" in j


def test_update_progress_endpoint_shape(app_client):
    client, *_ = app_client
    p = client.get("/api/update/progress").get_json()
    for key in ("state", "downloaded", "total", "pct"):
        assert key in p


def test_test_clip_endpoint_graceful_without_ffmpeg(app_client, monkeypatch):
    client, *_ = app_client
    # Force "no ffmpeg" so the endpoint reports a clean error instead of crashing.
    monkeypatch.setattr("aegis.media.resolve_ffmpeg", lambda *a, **k: None)
    j = client.post("/api/test-clip").get_json()
    assert j["ok"] is False and "ffmpeg" in j["detail"].lower()
