"""Sound feedback system — beep tones for user interaction."""

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None


class SoundFeedback:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._wake_beep = self._generate_beep(freq=880, duration=0.05)
        self._confirm_beep = self._generate_beep(freq=440, duration=0.1)
        self._error_beep = self._generate_beep(freq=220, duration=0.2)

    def _generate_beep(self, freq: float, duration: float) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        return (np.sin(2 * np.pi * freq * t) * 0.5 * 32767).astype(np.int16)

    def play_wake(self) -> None:
        """Short high beep — wake word detected."""
        self._play(self._wake_beep)

    def play_searching(self) -> None:
        """Confirmation beep — processing started."""
        self._play(self._confirm_beep)

    def play_error(self) -> None:
        """Low beep — error occurred."""
        self._play(self._error_beep)

    def _play(self, audio: np.ndarray) -> None:
        sd.play(audio, self.sample_rate, blocking=False)
