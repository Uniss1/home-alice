"""Streaming speech-to-text via Vosk."""

import json

import numpy as np

try:
    import vosk
except ImportError:
    vosk = None  # type: ignore[assignment]  # Mocked in tests


class VoskSTT:
    """Fast streaming STT for short commands using Vosk."""

    def __init__(self, model_path: str, sample_rate: int = 16000):
        self._model_path = model_path
        self._sample_rate = sample_rate
        self._model = vosk.Model(model_path)
        self.recognizer = vosk.KaldiRecognizer(self._model, sample_rate)

    def feed_frame(self, frame: np.ndarray) -> str | None:
        """Feed audio frame. Return recognized text or None if incomplete."""
        if self.recognizer.AcceptWaveform(frame.tobytes()):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        return None

    def get_partial(self) -> str:
        """Get current partial recognition result."""
        result = json.loads(self.recognizer.PartialResult())
        return result.get("partial", "")

    def reset(self) -> None:
        """Reset recognizer for new utterance."""
        self.recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate)
