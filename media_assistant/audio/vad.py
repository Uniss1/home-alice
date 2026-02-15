"""Voice Activity Detection via Silero VAD."""

import numpy as np

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]  # Mocked in tests on non-Windows


class VoiceActivityDetector:
    """Detect speech in audio frames using Silero VAD."""

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self.model, _ = torch.hub.load("snakers4/silero-vad", "silero_vad")

    def is_speech(self, frame: np.ndarray, sample_rate: int = 16000) -> bool:
        """Return True if frame contains speech."""
        audio_float = frame.astype(np.float32) / 32768.0
        tensor = torch.FloatTensor(audio_float)
        confidence = self.model(tensor, sample_rate)
        return confidence.item() > self.threshold

    def reset(self) -> None:
        """Reset internal state between utterances."""
        self.model.reset_states()
