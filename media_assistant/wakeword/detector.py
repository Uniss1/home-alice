"""Wake word detection via OpenWakeWord."""

import numpy as np

try:
    import openwakeword
except ImportError:
    openwakeword = None  # type: ignore[assignment]  # Mocked in tests on non-Windows


class WakeWordDetector:
    """Detect wake word in audio frames using OpenWakeWord."""

    def __init__(self, model_path: str, threshold: float = 0.8):
        self.model = openwakeword.Model(wakeword_models=[model_path])
        self.threshold = threshold

    def process_frame(self, frame: np.ndarray) -> float:
        """Return confidence score for wake word in frame (0.0-1.0)."""
        scores = self.model.predict(frame)
        return max(scores.values())

    def detected(self, frame: np.ndarray) -> bool:
        """Return True if wake word detected above threshold."""
        return self.process_frame(frame) >= self.threshold

    def reset(self) -> None:
        """Reset detector state."""
        self.model.reset()
