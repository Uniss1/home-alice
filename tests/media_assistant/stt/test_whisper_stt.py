"""Tests for WhisperSTT with mocked faster-whisper."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.stt.whisper_stt import WhisperSTT


class TestTranscribeReturnsText:
    @patch("media_assistant.stt.whisper_stt.faster_whisper")
    def test_transcribe_joins_segments(self, mock_fw):
        """Segments from whisper should be joined into a single string."""
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model

        seg1 = MagicMock()
        seg1.text = "включи"
        seg2 = MagicMock()
        seg2.text = "музыку"
        mock_model.transcribe.return_value = (iter([seg1, seg2]), None)

        stt = WhisperSTT()
        audio = np.random.randint(-1000, 1000, 16000, dtype=np.int16)
        result = stt.transcribe(audio)

        assert result == "включи музыку"
        mock_model.transcribe.assert_called_once()


class TestTranscribeReturnsLowercase:
    @patch("media_assistant.stt.whisper_stt.faster_whisper")
    def test_transcribe_lowercases_output(self, mock_fw):
        """Output should be lowercased and stripped."""
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model

        seg = MagicMock()
        seg.text = " Привет Мир "
        mock_model.transcribe.return_value = (iter([seg]), None)

        stt = WhisperSTT()
        result = stt.transcribe(np.zeros(16000, dtype=np.int16))

        assert result == "привет мир"


class TestTranscribeEmptyAudio:
    @patch("media_assistant.stt.whisper_stt.faster_whisper")
    def test_transcribe_empty_segments(self, mock_fw):
        """Empty/silent audio → empty string."""
        mock_model = MagicMock()
        mock_fw.WhisperModel.return_value = mock_model
        mock_model.transcribe.return_value = (iter([]), None)

        stt = WhisperSTT()
        result = stt.transcribe(np.zeros(16000, dtype=np.int16))

        assert result == ""
