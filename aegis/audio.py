"""An optional in-memory buffer for the default Windows playback device."""
from __future__ import annotations

import threading
import time
import wave
from collections import deque
from pathlib import Path

from .log import log


class SpeakerBuffer:
    def __init__(self, history: float):
        self._history = history
        self._lock = threading.Lock()
        self._samples: deque[tuple[float, bytes]] = deque()
        self._device = None
        self._stream = None
        self._channels = 0
        self._rate = 0

    def start(self) -> bool:
        try:
            import pyaudiowpatch as pa

            self._device = pa.PyAudio()
            output = self._device.get_default_wasapi_loopback()
            self._channels = int(output["maxInputChannels"])
            self._rate = int(output["defaultSampleRate"])
            self._continue = pa.paContinue
            self._stream = self._device.open(
                format=pa.paInt16, channels=self._channels, rate=self._rate,
                frames_per_buffer=1024, input=True, input_device_index=output["index"],
                stream_callback=self._receive,
            )
            return True
        except Exception as exc:
            self.stop()
            log(f"Speaker audio unavailable: {exc}")
            return False

    def _receive(self, data, frame_count, time_info, _status):
        now = time.monotonic()
        lag = time_info["current_time"] - time_info["input_buffer_adc_time"]
        start = now - (lag if 0 < lag < 1 else frame_count / self._rate)
        with self._lock:
            if data:
                self._samples.append((start, data))
            while self._samples and self._samples[0][0] < now - self._history:
                self._samples.popleft()
        return None, self._continue

    def stop(self) -> None:
        try:
            if self._stream is not None:
                self._stream.close()
        except OSError as exc:
            log(f"Could not close the speaker stream: {exc}")
        self._stream = None
        device, self._device = self._device, None
        if device is not None:
            try:
                device.terminate()
            except OSError as exc:
                log(f"Could not release the speaker device: {exc}")

    def write(self, spans: list[tuple[float, float]], path: Path) -> None:
        """Write speaker samples for the chosen video spans, filling gaps with silence."""
        with self._lock:
            samples = list(self._samples)
        frame_bytes = self._channels * 2
        with wave.open(str(path), "wb") as out:
            out.setparams((self._channels, 2, self._rate, 0, "NONE", "not compressed"))
            for start, stop in spans:
                frames = round((stop - start) * self._rate)
                pcm = bytearray(frames * frame_bytes)
                for at, data in samples:
                    if at >= stop:
                        break
                    offset = round((at - start) * self._rate)
                    first = max(0, -offset)
                    past = min(len(data) // frame_bytes, frames - offset)
                    if first < past:
                        begin = (offset + first) * frame_bytes
                        end = (offset + past) * frame_bytes
                        pcm[begin:end] = data[first * frame_bytes:past * frame_bytes]
                out.writeframesraw(pcm)
