import time
from types import SimpleNamespace
from pathlib import Path

from aegis.clips import Catalog, Clip
from aegis.engine import Engine, format_caption
from aegis.uploaders.base import UploadResult


def test_sharing_can_be_manual_only(cfg, data_dir, monkeypatch):
    cfg.set("uploads.automatic", False)
    catalog = Catalog()
    path = data_dir / "clip.mp4"
    path.touch()
    clip = Clip(id="clip", path=str(path), created=1)
    catalog.add(clip)
    calls = []

    def send(file, caption):
        calls.append((file, caption))
        return UploadResult(True)

    monkeypatch.setattr("aegis.engine.uploaders.build_enabled",
                        lambda _: [SimpleNamespace(name="gallery"), SimpleNamespace(name="telegram", send=send)])
    engine = Engine(cfg, catalog)
    assert engine.fan_out(clip, "Clip", automatic=True) == {"gallery": "ok"}
    assert not calls
    assert engine.fan_out(clip, "Clip") == {"gallery": "ok", "telegram": "ok"}
    assert calls == [(path, "Clip")]


def _gsi(kills, kmap="de_dust2", rnd=1, team="T"):
    return {"player": {"match_stats": {"kills": kills}, "team": team},
            "map": {"name": kmap, "round": rnd}}


class FakeRecorder:
    """Stand-in recorder that 'saves' by writing a tiny file."""
    def __init__(self):
        self.calls = 0
        self.ranges = None
    def start(self): pass
    def stop(self): pass
    def save(self, seconds, out_path: Path, ranges=None):
        self.calls += 1
        self.ranges = ranges
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"x" * 1024)
        return out_path
    def status(self):
        return {"backend": "fake", "capturing": True, "encoder": "fake"}


# ───────── caption formatting ─────────
def test_caption_variants():
    assert format_caption(1, "de_dust2", 4, "T") == "Kill on de_dust2 (round 4, T-side)"
    assert format_caption(5, "de_nuke", 22, "CT").startswith("ACE")
    assert format_caption(7, "de_vertigo", 0, "?") == "7K on de_vertigo"  # no round -> no suffix


# ───────── delta-based kill detection ─────────
def test_first_tick_syncs_without_firing(cfg):
    cfg.set("engine.debounce_sec", 999)
    eng = Engine(cfg, Catalog())
    eng.handle_payload(_gsi(3))           # connecting mid-match at 3 kills
    assert eng.status()["pending_kills"] == 0


def test_new_kills_accumulate(cfg):
    cfg.set("engine.debounce_sec", 999)
    eng = Engine(cfg, Catalog())
    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(1))
    eng.handle_payload(_gsi(3))           # +2 at once (double)
    assert eng.status()["pending_kills"] == 3


def test_kill_count_decrease_resets(cfg):
    cfg.set("engine.debounce_sec", 999)
    eng = Engine(cfg, Catalog())
    eng.handle_payload(_gsi(5))
    eng.handle_payload(_gsi(6))
    assert eng.status()["pending_kills"] == 1
    eng.handle_payload(_gsi(2))           # new match / reset
    assert eng.status()["pending_kills"] == 0


def test_partial_gsi_and_spectator_updates_preserve_local_streak(cfg):
    cfg.set("engine.debounce_sec", 999)
    eng = Engine(cfg, Catalog())
    local = _gsi(5)
    local["provider"] = {"steamid": "1"}
    local["player"]["steamid"] = "1"
    eng.handle_payload(local)
    local["player"]["match_stats"]["kills"] = 6
    eng.handle_payload(local)

    eng.handle_payload({"provider": {"steamid": "1"}})
    spectator = _gsi(15)
    spectator["provider"] = {"steamid": "1"}
    spectator["player"]["steamid"] = "2"
    eng.handle_payload(spectator)
    eng.handle_payload(local)

    assert eng.status()["gsi_connected"] is True
    assert eng.status()["pending_kills"] == 1
    eng._timer.cancel()


def test_deathmatch_kills_advance_baseline_without_queuing_clips(cfg, monkeypatch):
    eng = Engine(cfg, Catalog())
    monkeypatch.setattr(eng, "_arm_timer", lambda: None)
    for kills in range(45):
        event = _gsi(kills)
        event["map"]["mode"] = "deathmatch"
        eng.handle_payload(event)
    assert eng.status()["pending_kills"] == 0
    assert eng.status()["automatic_highlights"] is False

    cfg.set("engine.highlight_modes", "all")
    event = _gsi(45)
    event["map"]["mode"] = "deathmatch"
    eng.handle_payload(event)
    assert eng.status()["pending_kills"] == 1

    cfg.set("engine.highlight_modes", "competitive")
    for kills in (0, 1):
        event = _gsi(kills)
        event["map"]["mode"] = "competitive"
        eng.handle_payload(event)
    assert eng.status()["pending_kills"] == 1
    assert eng.status()["automatic_highlights"] is True
    cfg.set("engine.highlight_modes", "off")
    eng._save_clip()
    assert eng.status()["pending_kills"] == 0
    assert eng.status()["automatic_highlights"] is False


# ───────── debounce -> save -> catalog -> fan-out ─────────
def test_streak_saves_and_catalogs(cfg):
    cfg.set("engine.debounce_sec", 0.1)
    cfg.set("uploads.gallery.enabled", True)
    eng = Engine(cfg, Catalog())
    eng.recorder = FakeRecorder()

    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(1))
    eng.handle_payload(_gsi(2))           # double; timer (re)armed
    time.sleep(0.4)                        # let the debounce fire

    assert eng.recorder.calls == 1
    assert len(eng.recorder.ranges) == 1
    start, stop = eng.recorder.ranges[0]
    assert 3 <= stop - start < 4
    clips = eng.catalog.list()
    assert len(clips) == 1
    assert clips[0].kills == 2
    assert clips[0].uploads.get("gallery") == "ok"


def test_min_kills_gate_skips_solo(cfg):
    cfg.set("engine.debounce_sec", 0.1)
    cfg.set("engine.min_kills", 2)
    eng = Engine(cfg, Catalog())
    eng.recorder = FakeRecorder()

    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(1))           # solo kill only
    time.sleep(0.4)

    assert eng.recorder.calls == 0
    assert eng.catalog.list() == []

def test_competitive_round_groups_widely_spaced_kills_after_spectating(cfg, monkeypatch):
    engine = Engine(cfg, Catalog())
    engine.recorder = FakeRecorder()
    now = time.monotonic()
    timers = []

    def start_timer(timer):
        timers.append(timer)

    monkeypatch.setattr("aegis.engine.time.monotonic", lambda: now)
    monkeypatch.setattr("aegis.engine.threading.Timer.start", start_timer)

    def payload(kills, phase="live", round_index=3, player="local"):
        update = _gsi(kills, rnd=round_index)
        update["map"].update(mode="competitive", phase="live")
        update["round"] = {"phase": phase}
        update["provider"] = {"steamid": "local"}
        update["player"]["steamid"] = player
        engine.handle_payload(update)

    payload(0)
    payload(1)
    now += 70
    payload(2)
    assert not timers
    assert engine.status()["pending_kills"] == 2

    payload(10, phase="over", round_index=4, player="teammate")
    assert len(timers) == 1
    now += timers[0].interval
    timers[0].function()
    payload(2, phase="over", round_index=4)

    assert [(clip.round_n, clip.kills) for clip in engine.catalog.list()] == [(4, 2)]
    assert len(engine.recorder.ranges) == 2
    assert len(timers) == 1


def test_merge_round_clips_keeps_originals_and_sums_kills(cfg, data_dir, monkeypatch):
    engine = Engine(cfg, Catalog())
    sources = []
    for i, kills in enumerate((1, 2)):
        source = data_dir / f"source-{i}.mp4"
        source.write_bytes(b"source")
        sources.append(source)
        engine.catalog.add(Clip(id=str(i), path=str(source), created=i, kills=kills,
                                match_id="match", round_n=4, map_name="de_dust2"))

    def build(_ffmpeg, clips, output, **_options):
        assert clips == sources
        output.write_bytes(b"merged")
        return output

    monkeypatch.setattr("aegis.engine.media.resolve_ffmpeg", lambda _: "ffmpeg")
    monkeypatch.setattr("aegis.engine.media.quality_encode_args", lambda *_: [])
    monkeypatch.setattr("aegis.engine.media.build_montage", build)
    monkeypatch.setattr("aegis.engine.media.make_thumbnail", lambda *_: None)
    clip = engine.merge_round_clips(["1", "0"])

    assert (clip.kills, clip.round_n, clip.match_id) == (3, 4, "match")
    assert Path(clip.path).read_bytes() == b"merged"
    assert all(source.read_bytes() == b"source" for source in sources)
