from pathlib import Path

from aegis import polish, steam


def test_build_polish_cmd_with_intro(tmp_path):
    png = tmp_path / "intro.png"
    png.write_bytes(b"x")
    cmd = polish.build_polish_cmd(
        "ffmpeg", tmp_path / "a.mp4", tmp_path / "o.mp4", png, 30.0,
        fade=True, intro_seconds=3.0)
    j = " ".join(cmd)
    assert "-filter_complex" in cmd
    assert "scale2ref" in j and "overlay=0:0" in j   # intro scaled + overlaid
    assert "fade=t=in" in j and "fade=t=out" in j     # clip + intro fades


def test_build_polish_cmd_no_intro(tmp_path):
    cmd = polish.build_polish_cmd(
        "ffmpeg", tmp_path / "a.mp4", tmp_path / "o.mp4", None, 30.0,
        fade=True, intro_seconds=3.0)
    j = " ".join(cmd)
    assert "overlay" not in j and "scale2ref" not in j
    assert "fade=t=in" in j


def test_build_polish_cmd_short_clip_skips_fadeout(tmp_path):
    cmd = polish.build_polish_cmd(
        "ffmpeg", tmp_path / "a.mp4", tmp_path / "o.mp4", None, 0.5,
        fade=True, intro_seconds=3.0)
    assert "fade=t=out" not in " ".join(cmd)   # too short to fade out


def test_polish_disabled_returns_none(cfg, tmp_path):
    cfg.set("polish.enabled", False)
    assert polish.polish_clip(cfg, tmp_path / "x.mp4", 5, "de_dust2", "You", "") is None


def test_kill_big_labels():
    assert polish.KILL_BIG[5] == "ACE"
    assert polish.KILL_BIG[3] == "TRIPLE KILL"


def test_fetch_avatar_rejects_bad_ids():
    assert steam.fetch_avatar("") is None
    assert steam.fetch_avatar("not-a-steamid") is None
    assert steam.fetch_avatar(None) is None


def test_quality_encode_args_prefers_gpu(cfg, monkeypatch):
    from aegis import media, recorder
    monkeypatch.setattr(recorder, "_encoders_text", lambda f: "V..... h264_nvenc")
    assert "h264_nvenc" in media.quality_encode_args("ffmpeg", cfg)


def test_quality_encode_args_cpu_fallback(cfg, monkeypatch):
    from aegis import media, recorder
    monkeypatch.setattr(recorder, "_encoders_text", lambda f: "only libx264 here")
    assert "libx264" in media.quality_encode_args("ffmpeg", cfg)


def test_polish_cmd_uses_given_encoder(tmp_path):
    png = tmp_path / "i.png"
    png.write_bytes(b"x")
    cmd = polish.build_polish_cmd("ffmpeg", tmp_path / "a.mp4", tmp_path / "o.mp4",
                                  png, 30.0, fade=True, intro_seconds=3.0,
                                  encode_args=["-c:v", "h264_nvenc", "-cq", "23"])
    assert "h264_nvenc" in cmd and "libx264" not in cmd
