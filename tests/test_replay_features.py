import errno
import time
from types import SimpleNamespace

import pytest

from aegis.clips import Catalog
from aegis.engine import Engine, playback_markers


def test_markers_follow_joined_video_and_skip_omitted_time():
    assert playback_markers([(11.25, 1, 1), (16, 1, 1), (21.5, 2, 2)], ((10, 12), (20, 22))) == [
        {"time": 1.25, "kills": 1, "round": 1}, {"time": 3.5, "kills": 2, "round": 2},
    ]


def test_manual_only_keeps_local_kills_and_separates_same_map_matches(cfg, monkeypatch):
    cfg.set("engine.highlight_modes", "off")
    eng = Engine(cfg, Catalog())
    now = time.monotonic()

    def payload(kills, phase, round_n, player="local"):
        eng.handle_payload({"provider": {"steamid": "local"}, "player": {
            "steamid": player, "team": "CT", "match_stats": {"kills": kills},
        }, "map": {"name": "de_mirage", "mode": "competitive", "phase": phase, "round": round_n}})

    def save(_, destination, ranges):
        destination.write_bytes(b"clip")
        return destination

    eng.recorder = SimpleNamespace(save=save, last_saved_spans=((now - 1, now + 5),))
    monkeypatch.setattr("aegis.engine.media.resolve_ffmpeg", lambda *args: "")
    payload(0, "live", 0)
    payload(2, "live", 0)
    payload(23, "live", 0, player="teammate")
    first = eng.catalog.get(eng.save_replay()["clip_id"])
    assert first.match_id and first.map_name == "de_mirage"
    assert first.round_n == 1
    assert [marker["kills"] for marker in first.kill_markers] == [2]

    payload(2, "gameover", 13)
    payload(2, "live", 0)
    payload(3, "live", 0)
    second = eng.catalog.get(eng.save_replay()["clip_id"])
    assert second.match_id != first.match_id
    assert [marker["kills"] for marker in second.kill_markers] == [1]


@pytest.mark.parametrize(("error", "expected"), [
    (OSError(errno.ENOSPC, "full"), "The save drive is full."),
    (PermissionError(errno.EACCES, "unwritable"), "The clip folder is unavailable or unwritable."),
])
def test_shortcut_receipt_reports_write_failure(cfg, monkeypatch, error, expected):
    eng = Engine(cfg, Catalog())
    notices = []
    eng.notify_replay = notices.append

    def unavailable():
        raise error

    monkeypatch.setattr(eng, "clips_dir", unavailable)
    eng.save_shortcut_replay()
    assert not eng.replay_receipt["ok"]
    assert eng.status()["replay_receipt"]["message"] == expected
    assert notices == [expected]


def test_shortcut_success_and_warmup_receipts(cfg, monkeypatch):
    eng = Engine(cfg, Catalog())
    eng.recorder = SimpleNamespace(save=lambda *args: None, status=lambda: {"state": "starting"})
    eng.save_shortcut_replay()
    initial = eng.replay_receipt
    assert initial["message"] == "The replay buffer is still warming up."
    monkeypatch.setattr(eng, "save_replay", lambda: {"ok": True})
    eng.save_shortcut_replay()
    assert eng.replay_receipt["ok"] and initial["id"] != eng.replay_receipt["id"]


def test_storage_check_reports_both_locations_without_modifying_clips(cfg, monkeypatch):
    eng = Engine(cfg, Catalog())
    folder = eng.clips_dir()
    existing = folder / "keep.mp4"
    existing.write_bytes(b"clip")
    cfg.set("storage.clips_dir", str(folder))
    monkeypatch.setattr("aegis.storage.shutil.disk_usage", lambda path: SimpleNamespace(
        free=17 if path == folder else 6 * 1024**3,
    ))
    eng.storage_status()
    for _ in range(100):
        if status := eng.storage_status():
            break
        time.sleep(.01)
    assert status["clips"] == {"available": True, "free_bytes": 17, "low": True}
    assert status["buffer"]["low"] is False
    assert existing.read_bytes() == b"clip"


def test_audio_source_preserves_legacy_opt_in_and_rejects_unknown_sources(app_client):
    client, cfg, _, _ = app_client
    cfg.set("recording.speaker_audio", True)
    assert cfg.audio_source() == "desktop"
    assert client.post("/api/config", json={"recording": {"audio_source": "invalid"}}).status_code == 400
    assert client.post("/api/config", json={"recording": {"audio_source": "cs2"}}).status_code == 200
    assert cfg.audio_source() == "cs2"
    cfg.set("recording.audio_source", "off")
    assert cfg.audio_source() == "off"
