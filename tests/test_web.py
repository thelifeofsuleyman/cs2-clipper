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
