import io
import sys
import time
from types import SimpleNamespace

import pytest

from aegis import media, recorder, update
from aegis.clips import Clip
from aegis.health import COUNTERS, HealthMetrics


def test_highlight_window_and_direct_gpu_capture_preset(app_client, monkeypatch):
    client, cfg, _, _ = app_client
    change = {"engine": {"highlight_window": "custom", "highlight_before": 3.25, "highlight_after": 1.75}}
    assert client.post("/api/config", json=change).status_code == 200
    assert recorder.highlight_ranges([10, 20], *cfg.highlight_padding()) == [(6.75, 11.75), (16.75, 21.75)]
    assert client.post("/api/config", json={"engine": {"highlight_after": True}}).status_code == 400
    assert client.post("/api/config", json={"engine": {"highlight_window": "competitive"},
                                           "recording": {"preset": "gpu_only"}}).status_code == 200
    assert recorder.highlight_ranges([10, 12], *cfg.highlight_padding()) == [(9.0, 10.75), (11.0, 12.75)]
    cfg.set("recording.prioritize_game_fps", False)
    monkeypatch.setattr(recorder, "_encoders_text", lambda _: "h264_nvenc libx264")
    assert recorder.capture_candidates("ffmpeg", cfg) == [("ddagrab-d3d11", "h264_nvenc")]
    assert recorder.capture_options(cfg, "h264_nvenc") == (0, 0, 30, "8M")
    monkeypatch.setattr(recorder, "_encoders_text", lambda _: "libx264 h264_qsv")
    assert recorder.capture_candidates("ffmpeg", cfg) == []


def test_batch_starts_after_gameover_and_exports_individual_files(app_client, data_dir, monkeypatch):
    client, _, catalog, engine = app_client
    small = data_dir / "small.mp4"
    small.write_bytes(b"small video")
    large = data_dir / "large.mp4"
    with large.open("wb") as video:
        video.truncate(10_000_001)
    for key, file in (("one", small), ("two", large)):
        catalog.add(Clip(id=key, path=str(file), title=key, created=1, match_id="match"))
    engine.handle_payload({"provider": {"steamid": "owner"}, "player": {"steamid": "observed"},
                           "map": {"phase": "live"}})
    assert not engine.can_batch_export()
    tries = []

    def encode(_ffmpeg, source, out, max_bytes, *, pause):
        assert source == large and max_bytes == 10_000_000 and not pause()
        if not tries:
            engine.handle_payload({"provider": {"steamid": "owner"}, "map": {"phase": "live"}})
            assert pause()
            tries.append("paused")
            raise media.ExportPaused
        out.write_bytes(b"fitted video")
        return True

    monkeypatch.setattr("aegis.batch_exports.media.reencode_to_fit", encode)
    queued = client.post("/api/batch-exports", json={"clip_ids": ["one", "two"], "max_mb": 10})
    assert queued.status_code == 202
    job_id = queued.json["job"]["id"]
    assert client.get(f"/exports/{job_id}/0").status_code == 404
    assert [item["state"] for item in client.get("/api/batch-exports").json["jobs"][0]["items"]] == [
        "queued", "queued",
    ]
    engine.handle_payload({"provider": {"steamid": "owner"}, "map": {"phase": "gameover"}})
    for _ in range(100):
        if tries:
            break
        time.sleep(.04)
    assert tries == ["paused"]
    assert client.get(f"/exports/{job_id}/1").status_code == 404
    engine.handle_payload({"provider": {"steamid": "owner"}, "map": {"phase": "gameover"}})
    for _ in range(100):
        job = client.get("/api/batch-exports").json["jobs"][0]
        if all(item["state"] == "ready" for item in job["items"]):
            break
        time.sleep(.04)
    assert client.get(f"/exports/{job_id}/0").data == b"small video"
    assert client.get(f"/exports/{job_id}/1").data == b"fitted video"
    assert client.delete(f"/api/batch-exports/{job_id}").status_code == 200
    assert large.stat().st_size == 10_000_001 and small.read_bytes() == b"small video"


def test_batch_encoder_stops_when_a_match_starts():
    started = time.monotonic()
    with pytest.raises(media.ExportPaused):
        media._run([sys.executable, "-c", "import time; time.sleep(15)"],
                   timeout=8, pause=lambda: time.monotonic() - started > .1)
    assert time.monotonic() - started < 4


def test_health_counts_start_disabled_and_report_only_opted_in_counters(app_client, monkeypatch, data_dir):
    client, cfg, _, engine = app_client
    engine.health.add(save_attempts=1, save_ms=20)
    assert client.get("/api/app-health").json["counts"] == {}
    assert not (data_dir / "health-metrics.json").exists()
    assert client.post("/api/config", json={"metrics": {"enabled": True}}).status_code == 200
    engine.health.add(capture_attempts=1, capture_ready=1, capture_start_ms=1200, save_attempts=1, saves=1, save_ms=40)
    engine.recorder._track_progress(io.BytesIO(
        b"frame=15\ndrop_frames=2\nprogress=continue\nframe=20\ndrop_frames=3\nprogress=end\n",
    ))
    monkeypatch.setattr(update.ReleaseChecker, "check", lambda *_a, **_k: update.ReleaseCheck(downloads=123))
    report = client.get("/api/app-health?downloads=1").json["counts"]
    assert set(report) == {*COUNTERS, "latest_release_downloads"}
    assert report["save_attempts"] == 1 and report["saves"] == 1
    assert report["frames_output"] == 20 and report["frames_dropped"] == 3
    assert report["latest_release_downloads"] == 123
    assert HealthMetrics(cfg).snapshot()["capture_start_ms"] == 1200
    assert client.post("/api/config", json={"metrics": {"enabled": False}}).status_code == 200
    assert client.get("/api/app-health?downloads=1").json["counts"] == {}


def test_latest_release_counts_include_only_official_packages(cfg, monkeypatch):
    tag = "v0.1.0"
    download = f"https://github.com/thelifeofsuleyman/cs2-clipper/releases/download/{tag}/"
    assets = [
        {"name": "AegisClipper-Setup.exe", "download_count": 8,
         "browser_download_url": download + "AegisClipper-Setup.exe"},
        {"name": "AegisClipper-portable.zip", "download_count": 3,
         "browser_download_url": download + "AegisClipper-portable.zip"},
        {"name": "test.zip", "download_count": 10, "browser_download_url": download + "test.zip"},
    ]
    monkeypatch.setattr(update.requests, "get",
                        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {
                            "tag_name": tag, "assets": assets,
                        }))
    release = update.ReleaseChecker(cfg).check()
    assert release.info is None and release.downloads == 11
