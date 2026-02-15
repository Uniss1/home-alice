"""Audio capture with microphone and WASAPI loopback via PyAudioWPatch."""

import time
import threading
from collections import deque
from dataclasses import dataclass
from queue import Queue, Empty

import numpy as np
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None  # type: ignore[assignment]  # Mocked in tests on non-Windows


@dataclass
class AudioFrame:
    """Synchronized audio frame from mic and loopback."""

    mic: np.ndarray  # int16, mono, 16kHz
    loopback: np.ndarray  # int16, mono, 16kHz
    timestamp: float


class AudioCapture:
    """Captures microphone input and WASAPI loopback simultaneously."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_size: int = 512,
        mic_device: str | None = None,
        buffer_seconds: float = 2.0,
    ):
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._mic_device = mic_device
        self._buffer_seconds = buffer_seconds

        self._pa: pyaudio.PyAudio | None = None
        self._mic_stream = None
        self._loopback_stream = None
        self._running = False

        self._mic_buffer: deque[np.ndarray] = deque(
            maxlen=int(buffer_seconds * sample_rate / frame_size)
        )
        self._loopback_buffer: deque[np.ndarray] = deque(
            maxlen=int(buffer_seconds * sample_rate / frame_size)
        )
        self._frame_queue: Queue[AudioFrame] = Queue()

        self._loopback_rate: float = 0.0
        self._loopback_channels: int = 0

        self._mic_thread: threading.Thread | None = None
        self._loopback_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start mic + loopback capture threads."""
        self._pa = pyaudio.PyAudio()

        loopback_device = self._pa.get_wasapi_loopback()
        self._loopback_rate = loopback_device["defaultSampleRate"]
        self._loopback_channels = loopback_device["maxInputChannels"]

        # Calculate loopback frame size to match time duration of mic frame
        duration_per_frame = self._frame_size / self._sample_rate
        loopback_frame_samples = int(
            self._loopback_rate * duration_per_frame * self._loopback_channels
        )

        self._mic_stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=self._frame_size,
        )

        self._loopback_stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._loopback_channels,
            rate=int(self._loopback_rate),
            input=True,
            input_device_index=loopback_device["index"],
            frames_per_buffer=loopback_frame_samples,
        )

        self._running = True

        self._mic_thread = threading.Thread(target=self._mic_reader, daemon=True)
        self._loopback_thread = threading.Thread(
            target=self._loopback_reader, daemon=True
        )
        self._sync_thread = threading.Thread(target=self._synchronizer, daemon=True)

        self._mic_thread.start()
        self._loopback_thread.start()
        self._sync_thread.start()

    def stop(self) -> None:
        """Stop capture, release resources."""
        self._running = False

        if self._mic_stream is not None:
            self._mic_stream.stop_stream()
            self._mic_stream.close()
            self._mic_stream = None

        if self._loopback_stream is not None:
            self._loopback_stream.stop_stream()
            self._loopback_stream.close()
            self._loopback_stream = None

        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def read_frame(self, timeout: float = 1.0) -> AudioFrame | None:
        """Read next synchronized frame. Returns None on timeout."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except Empty:
            return None

    def _mic_reader(self) -> None:
        """Read mic data into ring buffer."""
        while self._running:
            try:
                data = self._mic_stream.read(
                    self._frame_size, exception_on_overflow=False
                )
                frame = np.frombuffer(data, dtype=np.int16)
                self._mic_buffer.append(frame)
            except Exception:
                if not self._running:
                    break

    def _loopback_reader(self) -> None:
        """Read loopback data into ring buffer, resample to mono 16kHz."""
        duration_per_frame = self._frame_size / self._sample_rate
        loopback_frame_samples = int(
            self._loopback_rate * duration_per_frame * self._loopback_channels
        )
        while self._running:
            try:
                data = self._loopback_stream.read(
                    loopback_frame_samples, exception_on_overflow=False
                )
                raw = np.frombuffer(data, dtype=np.int16)
                resampled = self._resample_to_mono_16k(raw)
                self._loopback_buffer.append(resampled)
            except Exception:
                if not self._running:
                    break

    def _resample_to_mono_16k(self, raw: np.ndarray) -> np.ndarray:
        """Convert raw loopback audio to mono 16kHz int16."""
        samples = raw.copy()

        # Stereo → mono: average channels
        if self._loopback_channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        # Resample if rate differs
        if self._loopback_rate != self._sample_rate:
            target_len = self._frame_size
            indices = np.linspace(0, len(samples) - 1, target_len)
            samples = np.interp(indices, np.arange(len(samples)), samples)

        return samples.astype(np.int16)

    def _synchronizer(self) -> None:
        """Combine mic + loopback buffers into AudioFrames."""
        while self._running:
            if self._mic_buffer and self._loopback_buffer:
                mic = self._mic_buffer.popleft()
                loopback = self._loopback_buffer.popleft()
                frame = AudioFrame(
                    mic=mic,
                    loopback=loopback,
                    timestamp=time.time(),
                )
                self._frame_queue.put(frame)
            else:
                time.sleep(0.001)
