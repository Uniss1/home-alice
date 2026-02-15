"""Tests for STTRouter."""

from unittest.mock import MagicMock
import numpy as np
import pytest

from media_assistant.stt.router import STTRouter


class TestRouterUsesWhisperForGeneral:
    def test_general_context_uses_whisper(self):
        """General context should route to Whisper."""
        mock_whisper = MagicMock()
        mock_vosk = MagicMock()
        mock_whisper.transcribe.return_value = "включи музыку"

        router = STTRouter(whisper=mock_whisper, vosk=mock_vosk)
        audio = np.zeros(16000, dtype=np.int16)
        result = router.transcribe(audio, context="general")

        assert result == "включи музыку"
        mock_whisper.transcribe.assert_called_once_with(audio)
        mock_vosk.feed_frame.assert_not_called()


class TestRouterUsesVoskForConfirmation:
    def test_confirmation_context_uses_vosk(self):
        """Confirmation context should route to Vosk streaming."""
        mock_whisper = MagicMock()
        mock_vosk = MagicMock()

        # Vosk returns None for first chunks, then "да"
        mock_vosk.feed_frame.side_effect = [None, None, "да"]

        router = STTRouter(whisper=mock_whisper, vosk=mock_vosk)
        audio = np.zeros(1536, dtype=np.int16)  # 3 chunks of 512
        result = router.transcribe(audio, context="confirmation")

        assert result == "да"
        mock_whisper.transcribe.assert_not_called()

    def test_confirmation_returns_empty_when_no_result(self):
        """If Vosk never returns a result, return empty string."""
        mock_whisper = MagicMock()
        mock_vosk = MagicMock()
        mock_vosk.feed_frame.return_value = None

        router = STTRouter(whisper=mock_whisper, vosk=mock_vosk)
        audio = np.zeros(512, dtype=np.int16)
        result = router.transcribe(audio, context="confirmation")

        assert result == ""
