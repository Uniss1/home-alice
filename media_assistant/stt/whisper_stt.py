"""Speech-to-text via faster-whisper (batch mode)."""

import numpy as np

try:
    import faster_whisper
except ImportError:
    faster_whisper = None  # type: ignore[assignment]  # Mocked in tests


class WhisperSTT:
    """High-accuracy batch STT using faster-whisper."""

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "int8",
    ):
        self.model = faster_whisper.WhisperModel(
            model_name, device=device, compute_type=compute_type
        )

    def transcribe(self, audio: np.ndarray, language: str = "ru") -> str:
        """Transcribe audio array to text. Returns lowercase stripped text."""
        segments, _ = self.model.transcribe(audio, language=language)
        return " ".join(s.text for s in segments).strip().lower()
