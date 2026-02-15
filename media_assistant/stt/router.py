"""STT routing — Whisper for general, Vosk for confirmations."""

import numpy as np

from media_assistant.stt.whisper_stt import WhisperSTT
from media_assistant.stt.vosk_stt import VoskSTT


class STTRouter:
    """Route transcription to the appropriate STT engine."""

    def __init__(self, whisper: WhisperSTT, vosk: VoskSTT):
        self.whisper = whisper
        self.vosk = vosk

    def transcribe(self, audio: np.ndarray, context: str = "general") -> str:
        """Route to Vosk (confirmation) or Whisper (general)."""
        if context == "confirmation":
            for chunk in np.array_split(audio, max(1, len(audio) // 512)):
                result = self.vosk.feed_frame(chunk)
                if result:
                    return result
            return ""
        else:
            return self.whisper.transcribe(audio)
