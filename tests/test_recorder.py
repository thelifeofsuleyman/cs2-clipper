from pathlib import Path

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
