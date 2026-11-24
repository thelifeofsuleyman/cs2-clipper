import time
from pathlib import Path

from aegis.clips import Catalog
from aegis.engine import Engine, format_caption


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
