import shutil
import subprocess
from pathlib import Path

import pytest

from aegis import media


@pytest.mark.parametrize("use_audio", [False, True])
def test_montage_accepts_video_only_input(tmp_path, use_audio):
    bundled = Path(__file__).resolve().parents[1] / "packaging" / "vendor" / "ffmpeg.exe"
    ffmpeg = shutil.which("ffmpeg") or (str(bundled) if bundled.is_file() else None)
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")

    silent = tmp_path / "recording.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=s=160x90:d=0.25",
         "-c:v", "libx264", str(silent)],
        check=True, timeout=15, capture_output=True,
    )
    second = silent
    if use_audio:
        second = tmp_path / "sample.mp4"
        assert media.make_test_clip(ffmpeg, second, seconds=1)

    montage = tmp_path / "montage.mp4"
    assert media.build_montage(ffmpeg, [silent, second], montage,
                               encode_args=["-c:v", "libx264", "-preset", "ultrafast"]) == montage
    duration, audio = media.stream_info(ffmpeg, montage)
    assert duration > 0.3
    assert audio is use_audio
