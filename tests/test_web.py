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


def test_health_and_status(app_client):
    client, *_ = app_client
    h = client.get("/health").get_json()
    assert h["ok"] is True and "recorder" in h
    s = client.get("/api/status").get_json()
    assert "capturing" in s and "enabled_targets" in s


def test_config_get_and_post_roundtrip(app_client):
    client, cfg, *_ = app_client
    r = client.post("/api/config", json={"recording": {"preset": "low", "clip_seconds": 20}})
    rc = r.get_json()["config"]["recording"]
    assert rc["preset"] == "low" and rc["clip_seconds"] == 20
    assert client.get("/api/config").get_json()["recording"]["preset"] == "low"


def test_detect_endpoint_shape(app_client):
    client, *_ = app_client
    d = client.get("/api/detect").get_json()
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


def test_finish_setup_flips_first_run(app_client):
    client, cfg, *_ = app_client
    assert cfg.get("first_run") is True
    client.post("/api/finish-setup")
    assert cfg.get("first_run") is False


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
