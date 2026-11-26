import io
import json
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from aegis import audio, library_backup, media, recorder, winprocess
from aegis.clips import Catalog, Clip


def test_window_capture_uses_only_a_verified_hwnd_and_excludes_desktop_audio(app_client, monkeypatch):
    client, cfg, _, _ = app_client
    patch = {"recording": {"window_only": True, "audio_source": "desktop"}}
    assert client.post("/api/config", json=patch).status_code == 200
    assert cfg.audio_source() == "off"
    assert client.post("/api/capture-test").status_code == 409
    assert client.post("/api/audio-preview", json={"source": "desktop"}).status_code == 400
    monkeypatch.setattr(recorder, "_encoders_text", lambda _: "h264_nvenc libx264")
    choices = recorder.capture_candidates("ffmpeg", cfg)
    assert choices == [("gfxcapture-d3d11", "h264_nvenc"), ("gfxcapture", "h264_nvenc"), ("gfxcapture", "libx264")]
    args = recorder.capture_video_args(960, 540, 24, "libx264", "3M", "gfxcapture", True, window_handle=1234)
    chain = args[args.index("-filter_complex") + 1]
    assert chain.startswith("gfxcapture=hwnd=1234:") and "hwdownload" in chain
    assert "monitor_idx" not in chain
    with pytest.raises(ValueError, match="verified game window"):
        recorder.capture_video_args(0, 0, 30, "libx264", "3M", "gfxcapture", True)


def test_window_recorder_stops_when_foreground_moves_away(cfg, monkeypatch):
    cfg.set("recording.window_only", True)
    game_only = recorder.BuiltinRecorder(cfg)
    monkeypatch.setattr(recorder.sys, "platform", "win32")
    seen = iter([(42, 7), None, (84, 7)])
    monkeypatch.setattr(winprocess, "foreground_window", lambda executable: next(seen))
    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "ffmpeg")
    monkeypatch.setattr(recorder, "capture_candidates", lambda *_: [("gfxcapture", "libx264")])
    events = []

    def spawn(_ffmpeg, _method, _encoder, _segment_time, *, window_handle):
        events.append(window_handle)
        game_only._capture_window = window_handle
        if window_handle == 84:
            game_only._stop.set()

    def pause(state):
        events.append(state)

    monkeypatch.setattr(game_only, "_spawn", spawn)
    monkeypatch.setattr(game_only, "_game_closed", pause)
    monkeypatch.setattr(game_only._stop, "wait", lambda *_: None)
    game_only._run()
    assert events == [42, "paused_window", 84]


def test_per_mode_limits_keep_the_best_separate_from_manual_and_favorites(app_client, data_dir, monkeypatch):
    client, cfg, catalog, engine = app_client
    settings = {"engine": {"premier_clip_limit": 0, "competitive_clip_limit": 1, "deathmatch_clip_limit": 2}}
    assert client.post("/api/config", json=settings).status_code == 200
    assert client.post("/api/config", json={"engine": {"deathmatch_clip_limit": 21}}).status_code == 400
    assert not engine._mode_allows_highlights("premier")
    assert cfg.mode_clip_limit("competitive") == 1
    assert engine._mode_allows_highlights("deathmatch")
    monkeypatch.setattr(engine, "_arm_timer", lambda *_: None)
    monkeypatch.setattr(media, "resolve_ffmpeg", lambda _: "")

    def save(_seconds, path, _ranges):
        path.write_bytes(b"test clip")
        return path

    engine.recorder = SimpleNamespace(save=save)

    def tick(kills):
        engine.handle_payload({"provider": {"steamid": "1"}, "player": {"steamid": "1",
                              "match_stats": {"kills": kills}}, "map": {"name": "de_mirage", "mode": "deathmatch"}})

    tick(0)
    tick(2)
    engine._save_clip()
    tick(3)
    engine._save_clip()
    replaced = next(c for c in catalog.list() if c.kills == 1)
    tick(7)
    engine._save_clip()
    assert sorted(c.kills for c in catalog.list()) == [2, 4]
    assert not Path(replaced.path).exists()
    kept = next(c for c in catalog.list() if c.kills == 2)
    catalog.update(kept.id, favorite=True)
    tick(10)
    engine._save_clip()
    assert sorted(c.kills for c in catalog.list()) == [2, 3, 4]
    assert Path(kept.path).exists()


def test_collections_and_ready_batch_zip(app_client, data_dir):
    client, _, catalog, engine = app_client
    for name in ("one", "two"):
        video = data_dir / f"{name}.mp4"
        video.write_bytes(name.encode())
        catalog.add(Clip(id=name, path=str(video), created=1, title=name))
        response = client.post(f"/api/clips/{name}", json={"collections": ["Premier wins", " Mirage plays "]})
        assert response.json["collections"] == ["Premier wins", "Mirage plays"]
    assert client.post("/api/clips/one", json={"collections": [False]}).status_code == 400
    assert Catalog().get("one").collections == ["Premier wins", "Mirage plays"]
    engine.handle_payload({"provider": {"steamid": "local"}, "map": {"phase": "gameover"}})
    job = client.post("/api/batch-exports", json={"clip_ids": ["one", "two"], "max_mb": 10}).json["job"]
    for _ in range(100):
        result = client.get(f"/exports/{job['id']}/zip")
        if result.status_code == 200:
            break
        time.sleep(.03)
    assert result.status_code == 200
    with ZipFile(io.BytesIO(result.data)) as bundle:
        assert [bundle.read(name) for name in bundle.namelist()] == [b"one", b"two"]
    result.close()


@pytest.mark.parametrize("include_videos", [False, True])
def test_library_backup_restores_metadata_and_optional_videos(monkeypatch, data_dir, include_videos):
    catalog = Catalog()
    video = data_dir / "source.mp4"
    video.write_bytes(b"fixture")
    catalog.add(Clip(id="clip", path=str(video), created=1, title="Premier ace", favorite=True,
                     tags=["Mirage"], collections=["Premier wins"]))
    archive = data_dir / "roundlatch.zip"
    assert library_backup.create_backup(catalog, archive, include_videos) == {
        "clips": 1, "videos": int(include_videos),
    }
    with ZipFile(archive) as data:
        manifest = data.read("roundlatch-library.json")
        assert str(video).encode() not in manifest
        assert "path" not in json.loads(manifest)["clips"][0]
    restored = data_dir / "new"
    restored.mkdir()
    monkeypatch.setenv("AEGIS_DATA_DIR", str(restored))
    target = Catalog()
    summary = library_backup.restore_backup(target, archive, restored, budget=1000)
    assert summary == {"clips": 1, "videos": int(include_videos), "missing": int(not include_videos)}
    clip = Catalog().get("clip")
    assert (clip.title, clip.favorite, clip.tags, clip.collections) == ("Premier ace", True, ["Mirage"], ["Premier wins"])
    if include_videos:
        assert Path(clip.path).read_bytes() == b"fixture"
        assert library_backup.restore_backup(target, archive, restored, budget=1000)["videos"] == 0


def test_backup_api_and_audio_preview_stay_local(app_client, data_dir, monkeypatch):
    client, _, _, _ = app_client
    archive = data_dir / "library.zip"
    assert client.post("/api/library-backup", json={"action": "create", "path": str(archive)}).json["ok"]
    assert client.post("/api/library-backup", json={"action": "create", "path": str(archive)}).status_code == 409
    assert client.post("/api/library-backup", json={"action": "restore", "path": str(archive)}).json["ok"]
    monkeypatch.setattr(audio, "capture_preview", lambda source, destination: destination.write_bytes(b"WAV " + source.encode()))
    preview = client.post("/api/audio-preview", json={"source": "cs2"})
    assert preview.mimetype == "audio/wav" and preview.data == b"WAV cs2"


def test_backup_rejects_a_video_path_outside_the_restore_folder(data_dir):
    catalog = Catalog()
    catalog.add(Clip(id="clip", path=str(data_dir / "source.mp4"), created=1))
    original = data_dir / "valid.zip"
    library_backup.create_backup(catalog, original, False)
    with ZipFile(original) as archive:
        manifest = json.loads(archive.read("roundlatch-library.json"))
    manifest["clips"][0]["filename"] = "../outside.mp4"
    invalid = data_dir / "invalid.zip"
    with ZipFile(invalid, "w") as archive:
        archive.writestr("roundlatch-library.json", json.dumps(manifest))
    target = data_dir / "videos"
    target.mkdir()
    with pytest.raises(ValueError, match="invalid video name"):
        library_backup.restore_backup(catalog, invalid, target, 0)
    assert not list(target.iterdir())
    assert catalog.get("clip").path == str(data_dir / "source.mp4")


def test_live_audio_peak_silence_and_device_change(monkeypatch):
    now = [1.0]
    monkeypatch.setattr(audio, "time", SimpleNamespace(monotonic=lambda: now[0]))
    devices = iter(("speakers", "headphones"))
    monkeypatch.setattr(audio, "default_playback_endpoint", lambda: next(devices))
    tracker = audio.PlaybackDevice()
    buffer = audio.AudioBuffer(10, 1, 48000)
    buffer._append(1, (16384).to_bytes(2, "little", signed=True), 1)
    assert buffer.signal() == (.5, False)
    now[0] += 6
    assert buffer.signal() == (0, True)
    assert tracker.changed()


@pytest.mark.parametrize("source", ["desktop", "cs2"])
def test_audio_preview_writes_the_selected_source_and_stops_it(source, tmp_path, monkeypatch):
    monkeypatch.setattr(audio.sys, "platform", "win32")
    monkeypatch.setattr(audio, "time", SimpleNamespace(monotonic=lambda: 1.0, sleep=lambda _: None))
    monkeypatch.setattr(winprocess, "process_id", lambda executable: 42 if executable == "cs2.exe" else None)
    events = []
    payload = (4000).to_bytes(2, "little", signed=True) * 1000

    class PreviewBuffer(audio.AudioBuffer):
        def __init__(self, history):
            super().__init__(history, 1, 1000)
            self.ready = SimpleNamespace(wait=lambda _: True)

        def start(self):
            events.append("desktop")
            self._append(1.0, payload, 2.0)
            return True

        def refresh(self, pid):
            assert pid == 42
            events.append("cs2")
            self._append(1.0, payload, 2.0)

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(audio, "SpeakerBuffer", PreviewBuffer)
    monkeypatch.setattr(audio, "ProcessAudioBuffer", PreviewBuffer)
    output = tmp_path / "preview.wav"
    audio.capture_preview(source, output, seconds=1)
    assert events == [source, "stop"]
    with wave.open(str(output), "rb") as wav:
        assert wav.readframes(1000) == payload
