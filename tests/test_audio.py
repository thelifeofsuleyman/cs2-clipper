import io
import struct
import wave
from types import SimpleNamespace

import pytest

from aegis.audio import ProcessAudioBuffer, SpeakerBuffer


def test_speaker_audio_follows_the_video_cuts_and_fills_silence(tmp_path):
    speaker = SpeakerBuffer(20)
    speaker._rate, speaker._channels = 4, 1
    speaker._samples.extend([
        (10.25, struct.pack("<3h", 1, 2, 3)),
        (15.0, struct.pack("<4h", 7, 7, 7, 7)),
        (20.0, struct.pack("<2h", 4, 5)),
    ])
    out = tmp_path / "speaker.wav"
    speaker.write([(10, 11), (20, 21)], out)
    with wave.open(str(out), "rb") as audio:
        assert struct.unpack("<8h", audio.readframes(8)) == (0, 1, 2, 3, 4, 5, 0, 0)


def test_process_audio_uses_one_clock_offset_per_stream(monkeypatch):
    capture = ProcessAudioBuffer(10)
    first = 995_000_000
    pcm = bytes(441 * 4)
    stdout = io.BytesIO(bytes(12) + b"".join(
        struct.pack("<QI", first + packet * 100_000, len(pcm)) + pcm for packet in range(3)
    ))
    # The QPC continues updating between steps of the coarse monotonic clock.
    times = iter([99.512, 99.515, 99.525, 99.535])
    coarse = iter([50.0, 50.0, 50.016, 50.031, 50.031])
    monkeypatch.setattr("aegis.audio.time", SimpleNamespace(
        perf_counter=lambda: next(times), monotonic=lambda: next(coarse),
    ))
    capture._receive_pcm(SimpleNamespace(stdout=stdout))
    assert [start for start, _ in capture._samples] == pytest.approx([49.988, 49.998, 50.008], abs=1e-6)
