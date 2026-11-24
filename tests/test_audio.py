import struct
import wave

from aegis.audio import SpeakerBuffer


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
