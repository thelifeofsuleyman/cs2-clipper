"""Optional Windows playback audio buffered in memory."""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path

from .log import log


class AudioBuffer:
    def __init__(self, history: float, channels: int, rate: int):
        self._history = history
        self._lock = threading.Lock()
        self._samples: deque[tuple[float, bytes]] = deque()
        self._channels = channels
        self._rate = rate

    def _append(self, start: float, data: bytes, now: float) -> None:
        with self._lock:
            if data:
                self._samples.append((start, data))
            while self._samples and self._samples[0][0] < now - self._history:
                self._samples.popleft()

    def write(self, spans: list[tuple[float, float]], path: Path) -> None:
        """Write audio for the selected video spans and fill gaps with silence."""
        with self._lock:
            samples = sorted(self._samples, key=lambda sample: sample[0])
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


class SpeakerBuffer(AudioBuffer):
    def __init__(self, history: float):
        super().__init__(history, 0, 0)
        self._device = None
        self._stream = None

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
        self._append(start, data, now)
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


class ProcessAudioBuffer(AudioBuffer):
    """Receive 44.1 kHz stereo PCM from the packaged WASAPI helper."""

    _header = struct.Struct("<QI")

    def __init__(self, history: float):
        super().__init__(history, 2, 44100)
        self._lifecycle = threading.Lock()
        self._proc = None
        self._thread = None
        self._pid = None
        self._retry_at = 0.0
        self._closed = False
        self.ready = threading.Event()
        self.buffered = threading.Event()
        self.detail = ""
        self._supported = sys.platform == "win32" and sys.getwindowsversion().build >= 20348
        self._helper = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "packaging" / "vendor"))
        self._helper /= "aegis-process-audio.exe"

    def refresh(self, pid: int | None) -> None:
        with self._lifecycle:
            if self._closed:
                return
            now = time.monotonic()
            if pid == self._pid and self._proc is not None and self._proc.poll() is None:
                return
            if pid == self._pid and now < self._retry_at:
                return
            self._stop_stream()
            self._pid = pid
            if not self._supported:
                self.detail = "CS2-only audio requires Windows 11."
            elif not pid:
                self.detail = "Waiting for the CS2 audio process."
            elif not self._helper.is_file():
                self.detail = "The CS2 audio helper is missing. Reinstall Aegis Clipper."
            else:
                self._retry_at = now + 15
                try:
                    self._proc = subprocess.Popen(
                        [str(self._helper), str(pid), str(os.getpid())], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except OSError as exc:
                    self.detail = "Windows could not start the CS2 audio helper."
                    log(f"{self.detail} {exc}")
                    return
                self.detail = ""
                self._thread = threading.Thread(target=self._receive_pcm, args=(self._proc,), daemon=True)
                self._thread.start()

    def _receive_pcm(self, proc: subprocess.Popen) -> None:
        try:
            pipe = proc.stdout
            if pipe.read(self._header.size) != bytes(self._header.size):
                self.detail = "Windows could not start CS2-only audio capture."
                log(f"{self.detail} {proc.stderr.read(512).decode(errors='replace').strip()}")
                return
            self.ready.set()
            self.buffered.set()
            while header := pipe.read(self._header.size):
                stamp, size = self._header.unpack(header)
                if not 0 < size <= self._rate * 4 or size % 4:
                    raise ValueError("Invalid PCM packet size")
                data = pipe.read(size)
                if len(data) != size:
                    break
                now = time.monotonic()
                age = time.perf_counter() - stamp / 10_000_000 if stamp else -1
                self._append(now - (age if 0 <= age <= 2 else size / (4 * self._rate)), data, now)
        except (OSError, ValueError, struct.error) as exc:
            self.detail = "CS2-only audio capture was interrupted."
            log(f"{self.detail} {exc}")
        finally:
            self.ready.clear()

    def _stop_stream(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            self._thread.join()
            proc.stdout.close()
            proc.stderr.close()

    def stop(self) -> None:
        with self._lifecycle:
            self._closed = True
            self._stop_stream()
