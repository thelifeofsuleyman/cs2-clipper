import io
import struct
import wave
from math import pi, sin
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


@pytest.mark.parametrize("rate", [44100, 48000])
def test_desktop_pcm_stays_continuous_during_callback_jitter(tmp_path, monkeypatch, rate):
    from aegis import audio

    capture = SpeakerBuffer(10)
    capture._channels, capture._rate, capture._continue = 1, rate, 0
    block = 1024
    duration = block / rate
    expected = bytearray()
    for index in range(30):
        end = (index + 1) * duration
        jitter = (0, .013, -.004, .006)[index % 4]
        coarse = 50 + int(end / .015625) * .015625
        monkeypatch.setattr(audio, "time", SimpleNamespace(
            perf_counter=lambda: 100 + end + jitter, monotonic=lambda: coarse,
        ))
        pcm = struct.pack(f"<{block}h", *(round(9000 * sin(2 * pi * 440 * i / rate))
                                         for i in range(index * block, (index + 1) * block)))
        capture._receive(pcm, block, {"current_time": 10 + end, "input_buffer_adc_time": 10 + end - duration}, 0)
        expected.extend(pcm)

    start = capture._samples[0][0]
    wav = tmp_path / "tone.wav"
    capture.write([(start, start + 30 * duration)], wav)
    with wave.open(str(wav), "rb") as output:
        assert output.getframerate() == rate
        assert output.readframes(30 * block) == expected


def test_desktop_callback_overflow_leaves_silence(tmp_path, monkeypatch):
    capture = SpeakerBuffer(10)
    capture._channels, capture._rate, capture._continue = 1, 1000, 0
    capture._input_overflow = 2
    capture._clock_offset = 0
    times = iter((1.02, 1.06))
    monkeypatch.setattr("aegis.audio.time", SimpleNamespace(perf_counter=lambda: next(times)))
    block = struct.pack("<20h", *([100] * 20))
    capture._receive(block, 20, {"current_time": 0, "input_buffer_adc_time": 0}, 0)
    capture._receive(block, 20, {"current_time": 0, "input_buffer_adc_time": 0}, 2)
    wav = tmp_path / "overflow.wav"
    capture.write([(1, 1.06)], wav)
    with wave.open(str(wav), "rb") as output:
        assert output.readframes(60) == block + bytes(40) + block


def test_process_audio_keeps_invalid_packets_contiguous_and_preserves_timestamped_gaps(monkeypatch):
    capture = ProcessAudioBuffer(10)
    pcm = bytes(441 * 4)
    packet = lambda stamp: struct.pack("<QI", stamp, len(pcm)) + pcm
    stamps = (995_000_000, 0, 0, 996_000_000)
    stdout = io.BytesIO(bytes(12) + b"".join(packet(stamp) for stamp in stamps))
    times = iter((99.512, 99.515, 99.517, 99.549, 99.615))
    monkeypatch.setattr("aegis.audio.time", SimpleNamespace(
        perf_counter=lambda: next(times), monotonic=lambda: 50.0,
    ))
    capture._receive_pcm(SimpleNamespace(stdout=stdout))
    assert [start for start, _ in capture._samples] == pytest.approx([49.988, 49.998, 50.008, 50.088], abs=1e-6)
