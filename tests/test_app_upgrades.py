from pathlib import Path
import time
from types import SimpleNamespace

from aegis import media, recorder, update
from aegis.clips import Catalog, Clip


def test_low_impact_preset_limits_both_hardware_and_cpu_capture(app_client, monkeypatch):
    client, cfg, _, engine = app_client
    assert client.post("/api/config", json={"recording": {"preset": "light"}}).status_code == 200
    cfg.set("recording.fps", 60)
    cfg.set("recording.prioritize_game_fps", False)
    monkeypatch.setattr(recorder, "_encoders_text", lambda _: "h264_nvenc libx264")
    assert cfg.game_fps_priority()
    assert recorder.capture_options(cfg, "h264_nvenc") == (960, 540, 24, "3M")
    assert recorder.capture_options(cfg, "libx264") == (960, 540, 24, "3M")
    assert all(method != "ddagrab-d3d11" for method, _ in recorder.capture_candidates("ffmpeg", cfg))
    engine.recorder._stage = "ready"
    engine.recorder._proc = SimpleNamespace(poll=lambda: None)
    engine.recorder._encoder = "libx264"
    assert client.get("/api/status").json["recorder"]["cpu_encoding"]


def test_first_replay_check_requires_a_real_shortcut_save(app_client, data_dir, monkeypatch):
    client, cfg, catalog, engine = app_client
    monkeypatch.setattr(engine, "restart_recording", lambda: None)
    assert client.post("/api/finish-setup").json["ok"]
    assert client.get("/api/status").json["verify_first_replay"]
    verify = "/api/verify-replay"
    assert client.post(verify, json={"action": "confirm", "clip_id": "replay"}).status_code == 409
    video = data_dir / "replay.mp4"
    video.write_bytes(b"recorded video")
    catalog.add(Clip(id="replay", path=str(video), created=1))
    monkeypatch.setattr(engine, "save_replay", lambda: {"ok": True, "clip_id": "replay"})
    engine.save_shortcut_replay()
    assert client.post(verify, json={"action": "confirm", "clip_id": "replay"}).json["ok"]
    assert not cfg.get("verify_first_replay")
    assert client.post(verify, json={"action": "start"}).json["ok"]
    assert client.post(verify, json={"action": "confirm", "clip_id": "replay"}).status_code == 409


def test_highlight_receipt_tracks_mode_filter_warmup_failure_and_save(app_client, monkeypatch):
    client, _, _, engine = app_client

    class InertTimer:
        def __init__(self, delay, callback):
            pass

        def start(self):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr("aegis.engine.threading.Timer", InertTimer)
    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "")

    def game(kills, mode):
        engine.handle_payload({"provider": {"steamid": "1"}, "player": {"steamid": "1", "match_stats": {"kills": kills}},
                               "map": {"name": "de_mirage", "mode": mode, "phase": "live"}})

    def state():
        return client.get("/api/status").json["highlight_notice"]["state"]

    game(0, "deathmatch")
    game(1, "deathmatch")
    assert state() == "skipped"
    game(0, "competitive")
    game(1, "competitive")
    assert state() == "detected"
    engine.recorder = SimpleNamespace(save=lambda *_: None, status=lambda: {"state": "starting"})
    engine._save_clip(engine._timer_token)
    assert state() == "warming_up"
    engine.recorder.status = lambda: {"state": "error"}
    engine._save_clip(engine._timer_token)
    assert state() == "failed"

    def save(_seconds, target, _ranges):
        target.write_bytes(b"replay")
        return target

    engine.recorder.save = save
    engine._save_clip(engine._timer_token)
    assert state() == "saved"
    assert len(client.get("/api/clips").json["clips"]) == 1


def test_budget_trash_favorites_and_relink(app_client, data_dir, monkeypatch):
    client, cfg, catalog, engine = app_client
    folder = data_dir / "old"
    folder.mkdir()
    favorite = folder / "favorite.mp4"
    movie = folder / "movie.mp4"
    favorite.write_bytes(b"123456")
    movie.write_bytes(b"1234")
    catalog.add(Clip(id="favorite", path=str(favorite), created=1, favorite=True))
    catalog.add(Clip(id="movie", path=str(movie), created=1))
    monkeypatch.setattr(cfg, "clip_budget_bytes", lambda: 10)
    stash = "/api/deleted-clips/"
    assert client.post(stash + "favorite", json={"action": "trash"}).status_code == 409
    assert client.post(stash + "movie", json={"action": "trash"}).json["ok"]
    assert movie.exists() and Catalog().list(deleted=True)[0].id == "movie"
    assert client.get("/clip/movie/video").status_code == 404
    assert client.get("/api/clip-storage").json == {"used_bytes": 10, "budget_bytes": 10}
    assert "budget is full" in engine.save_replay()["detail"]
    assert client.post(stash + "movie", json={"action": "restore"}).json["ok"]
    assert client.get("/clip/movie/video").data == b"1234"
    assert client.post(stash + "movie", json={"action": "trash"}).json["ok"]
    assert client.post(stash + "movie", json={"action": "delete"}).json["ok"]
    assert not movie.exists() and favorite.exists()

    def save(_seconds, target, _ranges):
        target.write_bytes(b"12345")
        return target

    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "")
    engine.recorder = SimpleNamespace(save=save)
    assert "budget is full" in engine.save_replay()["detail"]
    assert not list(engine.clips_dir().glob("replay_*.mp4"))
    new = folder.rename(data_dir / "new")
    result = client.post("/api/clip-storage/relink", json={"old": str(folder), "new": str(new)})
    assert result.json == {"ok": True, "count": 1}
    relinked = Catalog().get("favorite")
    assert relinked.favorite and Path(relinked.path) == new / favorite.name


def test_trimmed_share_queues_during_game_and_encodes_only_selected_range(app_client, data_dir, monkeypatch):
    client, _, catalog, engine = app_client
    source = data_dir / "manual.mp4"
    source.write_bytes(b"original")
    catalog.add(Clip(id="manual", path=str(source), created=1))
    engine.handle_payload({"provider": {"steamid": "1"}, "map": {"phase": "live"}})
    selection = {"max_mb": 10, "start": 1.0, "end": 3.0}
    exported = client.post("/api/clips/manual/export", json=selection)
    assert exported.status_code == 409 and exported.json["queue_required"]

    def encode(_ffmpeg, input_file, output, limit, *, pause, window):
        assert input_file == source and limit == 10_000_000 and window == (1.0, 3.0) and not pause()
        output.write_bytes(b"selection")
        return True

    monkeypatch.setattr(media, "reencode_to_fit", encode)
    job = client.post("/api/batch-exports", json={"clip_ids": ["manual"], **selection}).json["job"]
    url = f"/exports/{job['id']}/0"
    assert client.get(url).status_code == 404
    engine.handle_payload({"provider": {"steamid": "1"}, "map": {"phase": "gameover"}})
    for _ in range(160):
        response = client.get(url)
        if response.status_code == 200:
            break
        time.sleep(.02)
    assert response.data == b"selection"
    assert source.read_bytes() == b"original"


def test_download_counts_are_separate_from_opt_in_failure_and_save_metrics(app_client, monkeypatch):
    client, _, _, engine = app_client
    monkeypatch.setattr(update.ReleaseChecker, "check", lambda *_a, **_k: update.ReleaseCheck(downloads=42))
    public = client.get("/api/app-health?downloads=1").json
    assert public["latest_release_downloads"] == 42 and public["counts"] == {}
    assert client.post("/api/config", json={"metrics": {"enabled": True}}).json["ok"]
    engine.recorder._capture_failed("test failure")

    def save(_seconds, target, _ranges):
        target.write_bytes(b"replay")
        return target

    engine.recorder.save = save
    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "")
    assert engine.save_replay()["ok"]
    engine.recorder.save = lambda *_: None
    assert not engine.save_replay()["ok"]
    counts = client.get("/api/app-health").json["counts"]
    assert counts["capture_errors"] == counts["save_errors"] == counts["clips_saved"] == 1
    assert not any(isinstance(value, str) for value in counts.values())
