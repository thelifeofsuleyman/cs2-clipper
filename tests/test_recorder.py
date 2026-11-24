import sys
import threading
from pathlib import Path

import pytest

from aegis import recorder


# ───────── pick_encoder ─────────
def test_pick_encoder_prefers_hardware():
    enc = "V..... libx264\nV..... h264_nvenc\nV..... h264_qsv"
    assert recorder.pick_encoder(enc, "auto") == "h264_nvenc"


def test_pick_encoder_respects_explicit_choice():
    enc = "libx264\nh264_qsv\nh264_nvenc"
    assert recorder.pick_encoder(enc, "qsv") == "h264_qsv"
    assert recorder.pick_encoder(enc, "x264") == "libx264"


def test_pick_encoder_falls_back_to_x264_when_no_hardware():
    assert recorder.pick_encoder("only libx264 here", "auto") == "libx264"


def test_pick_encoder_explicit_missing_falls_back_to_best_available():
    # asked for nvenc but only qsv present -> still gets a hardware encoder
    assert recorder.pick_encoder("h264_qsv", "nvenc") == "h264_qsv"


# ───────── pick_segments ─────────
def _entries(n):
    return [(Path(f"seg_{i:03d}.ts"), float(i)) for i in range(n)]


def test_pick_segments_returns_chronological_window():
    segs = recorder.pick_segments(_entries(20), clip_seconds=10, segment_time=2)
    names = [p.name for p in segs]
    assert names == sorted(names)          # chronological
    assert "seg_019.ts" not in names       # newest (in-progress) dropped
    assert len(segs) == 6                  # ceil(10/2)+1


def test_pick_segments_handles_few_segments():
    assert recorder.pick_segments(_entries(1), 30, 2)        # doesn't crash
    assert recorder.pick_segments([], 30, 2) == []


def test_pick_segments_caps_at_available():
    segs = recorder.pick_segments(_entries(3), clip_seconds=60, segment_time=2)
    assert len(segs) <= 3


# ───────── build_capture_cmd ─────────
def test_build_capture_cmd_ddagrab_nvenc():
    cmd = recorder.build_capture_cmd(
        "ffmpeg", Path("/buf"), width=1280, height=720, fps=30,
        encoder="h264_nvenc", bitrate="6M", segment_time=2, segment_wrap=25)
    joined = " ".join(cmd)
    assert "ddagrab" in joined and "scale=1280:720" in joined
    assert "h264_nvenc" in cmd
    assert cmd[cmd.index("-segment_wrap") + 1] == "25"
    assert cmd[cmd.index("-force_key_frames") + 1] == "expr:gte(t,n_forced*2)"


def test_capture_candidates_fall_back_to_software_and_other_input(cfg, monkeypatch):
    monkeypatch.setattr(recorder, "_encoders_text", lambda _: "h264_nvenc\nh264_qsv\nlibx264")
    assert recorder.capture_candidates("ffmpeg", cfg) == [
        ("ddagrab", "h264_nvenc"), ("ddagrab", "h264_qsv"), ("ddagrab", "libx264"),
        ("gdigrab", "h264_nvenc"), ("gdigrab", "h264_qsv"), ("gdigrab", "libx264"),
    ]


def test_build_capture_cmd_gdigrab_fallback_source_res():
    cmd = recorder.build_capture_cmd(
        "ffmpeg", Path("/buf"), width=0, height=0, fps=60,
        encoder="libx264", bitrate="16M", segment_time=2, segment_wrap=25,
        use_ddagrab=False)
    assert "gdigrab" in " ".join(cmd)
    assert "-vf" not in cmd                 # no scaling at source resolution
    assert "libx264" in cmd


# ───────── backend selection ─────────
def test_make_recorder_defaults_to_builtin(cfg):
    assert isinstance(recorder.make_recorder(cfg), recorder.BuiltinRecorder)


def test_make_recorder_obs_backend(cfg):
    cfg.set("recording.backend", "obs")
    assert isinstance(recorder.make_recorder(cfg), recorder.ObsRecorder)


def test_builtin_save_without_capture_returns_none(cfg, tmp_path):
    rec = recorder.BuiltinRecorder(cfg)
    # never started -> no process -> graceful None, no exception
    assert rec.save(30, tmp_path / "out.mp4") is None
    assert rec.status()["backend"] == "builtin"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process table")
def test_game_detection_matches_exact_process_name():
    assert recorder._process_running(Path(sys.executable).name.upper())
    assert not recorder._process_running("aegis-nonexistent-game-process.exe")


def test_process_detection_failure_cannot_start_recording(cfg, monkeypatch):
    rec = recorder.BuiltinRecorder(cfg)

    def fail(_):
        raise OSError("process snapshot unavailable")

    monkeypatch.setattr(recorder, "_process_running", fail)
    monkeypatch.setattr(rec, "_spawn", lambda *_: pytest.fail("Cannot record without a process match"))
    monkeypatch.setattr(rec._stop, "wait", lambda _: rec._stop.set())
    rec._run()
    assert not rec.status()["capturing"]
    assert "Windows could not check" in rec.status()["detail"]


def test_stalled_buffer_is_detected_even_if_current_segment_keeps_changing(cfg, monkeypatch):
    rec = recorder.BuiltinRecorder(cfg)
    rec._stage = "starting"
    rec._last_segment_at = 10.0
    closed, current = rec._bdir / "seg_001.ts", rec._bdir / "seg_002.ts"
    entries = [(closed, 100), (current, 110)]
    monkeypatch.setattr(rec, "_segment_entries", lambda: entries)
    monkeypatch.setattr(recorder.time, "monotonic", lambda: 12.0)
    assert not rec._check_segment_progress(2)
    assert rec._stage == "ready"

    monkeypatch.setattr(recorder.time, "monotonic", lambda: 23.0)
    entries[-1] = (current, 999)
    assert "stopped writing" in rec._check_segment_progress(2)


def test_slow_encoder_launch_does_not_block_recorder_status(cfg, monkeypatch):
    rec = recorder.BuiltinRecorder(cfg)
    entered, release, answered, terminated = (threading.Event() for _ in range(4))
    captured_status = {}

    def launch(*args, **kwargs):
        entered.set()
        assert release.wait(4)
        return object()

    def report():
        captured_status.update(rec.status())
        answered.set()

    monkeypatch.setattr(recorder.subprocess, "Popen", launch)
    monkeypatch.setattr("aegis.winjob.guard", lambda _: None)
    monkeypatch.setattr(rec, "_terminate", lambda _: terminated.set())
    spawn = threading.Thread(target=rec._spawn, args=("ffmpeg", "ddagrab", "libx264", 2))
    spawn.start()
    try:
        assert entered.wait(2)
        query = threading.Thread(target=report)
        query.start()
        assert answered.wait(1)
        assert captured_status["state"] == "starting"
        rec._stop.set()
    finally:
        release.set()
        spawn.join(5)
    query.join(2)
    assert terminated.is_set()
    assert rec._proc is None
