"""Regression tests for logical bugs found in the audit."""
import json
import time
from pathlib import Path

from aegis import config, paths, recorder
from aegis.clips import Catalog
from aegis.engine import Engine


# ── atomic JSON writes survive being read back (no truncation) ──
def test_atomic_write_replaces_cleanly(data_dir):
    target = data_dir / "x.json"
    paths.atomic_write_text(target, '{"a": 1}')
    paths.atomic_write_text(target, '{"a": 2, "b": 3}')
    assert json.loads(target.read_text()) == {"a": 2, "b": 3}
    assert not (data_dir / "x.json.tmp").exists()   # temp cleaned up


def test_config_save_is_atomic(cfg, data_dir):
    cfg.set("engine.min_kills", 3)
    cfg.save()
    assert json.loads(paths.config_file().read_text())["engine"]["min_kills"] == 3


# ── per-instance buffer dirs: two recorders never share a dir ──
def test_recorders_get_distinct_buffer_dirs(cfg):
    a = recorder.BuiltinRecorder(cfg)
    b = recorder.BuiltinRecorder(cfg)
    assert a._bdir != b._bdir
    assert a._bdir.is_dir() and b._bdir.is_dir()


def test_recorder_stop_is_safe_without_start(cfg):
    r = recorder.BuiltinRecorder(cfg)
    r.stop()                                   # must not raise even if never started
    assert not r._bdir.exists()                # cleaned up


# ── pending kills are NOT lost when the recorder can't save ──
class _FailRecorder:
    def start(self): pass
    def stop(self): pass
    def save(self, seconds, out): return None   # always "fails"
    def status(self): return {"backend": "fail", "capturing": False, "encoder": "x"}


class _OkRecorder:
    def start(self): pass
    def stop(self): pass
    def save(self, seconds, out: Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x" * 512)
        return out
    def status(self): return {"backend": "ok", "capturing": True, "encoder": "x"}


def _gsi(k):
    return {"player": {"match_stats": {"kills": k}, "team": "T"},
            "map": {"name": "de_dust2", "round": 1}}


def test_failed_save_keeps_pending_kills(cfg):
    cfg.set("engine.debounce_sec", 0.1)
    eng = Engine(cfg, Catalog())
    eng.recorder = _FailRecorder()
    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(2))
    time.sleep(0.4)                            # timer fires, save returns None
    # streak preserved (not discarded) so it can clip on a later kill
    assert eng.status()["pending_kills"] == 2
    assert eng.catalog.list() == []


def test_successful_save_consumes_pending_kills(cfg):
    cfg.set("engine.debounce_sec", 0.1)
    eng = Engine(cfg, Catalog())
    eng.recorder = _OkRecorder()
    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(2))
    time.sleep(0.4)
    assert eng.status()["pending_kills"] == 0
    assert len(eng.catalog.list()) == 1


def test_below_min_kills_drops_pending(cfg):
    cfg.set("engine.debounce_sec", 0.1)
    cfg.set("engine.min_kills", 2)
    eng = Engine(cfg, Catalog())
    eng.recorder = _OkRecorder()
    eng.handle_payload(_gsi(0))
    eng.handle_payload(_gsi(1))                # solo kill, below threshold
    time.sleep(0.4)
    assert eng.status()["pending_kills"] == 0   # intentionally dropped
    assert eng.catalog.list() == []


# ── Steam library detection helpers don't crash off-Windows ──
def test_detect_cs2_cfg_dir_never_raises():
    # On CI/Linux winreg is absent; must degrade to None, not raise.
    assert config.detect_cs2_cfg_dir() is None or isinstance(config.detect_cs2_cfg_dir(), Path)
