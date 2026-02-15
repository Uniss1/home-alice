"""Tests for VoskSTT with mocked Vosk."""

import json
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.stt.vosk_stt import VoskSTT


class TestVoskFeedFrame:
    @patch("media_assistant.stt.vosk_stt.vosk")
    def test_feed_frame_returns_text_on_complete(self, mock_vosk):
        """When recognizer accepts waveform, return recognized text."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model
        mock_recognizer = MagicMock()
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        mock_recognizer.AcceptWaveform.return_value = True
        mock_recognizer.Result.return_value = json.dumps({"text": "да"})

        stt = VoskSTT(model_path="model-ru")
        frame = np.zeros(512, dtype=np.int16)
        result = stt.feed_frame(frame)

        assert result == "да"

    @patch("media_assistant.stt.vosk_stt.vosk")
    def test_feed_frame_returns_none_when_incomplete(self, mock_vosk):
        """When recognizer hasn't completed, return None."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model
        mock_recognizer = MagicMock()
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        mock_recognizer.AcceptWaveform.return_value = False

        stt = VoskSTT(model_path="model-ru")
        result = stt.feed_frame(np.zeros(512, dtype=np.int16))

        assert result is None


class TestVoskPartialResult:
    @patch("media_assistant.stt.vosk_stt.vosk")
    def test_get_partial_returns_partial_text(self, mock_vosk):
        """get_partial should return current partial recognition."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model
        mock_recognizer = MagicMock()
        mock_vosk.KaldiRecognizer.return_value = mock_recognizer

        mock_recognizer.PartialResult.return_value = json.dumps(
            {"partial": "вклю"}
        )

        stt = VoskSTT(model_path="model-ru")
        assert stt.get_partial() == "вклю"


class TestVoskReset:
    @patch("media_assistant.stt.vosk_stt.vosk")
    def test_reset_creates_new_recognizer(self, mock_vosk):
        """Reset should create a fresh KaldiRecognizer."""
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model

        stt = VoskSTT(model_path="model-ru", sample_rate=16000)
        assert mock_vosk.KaldiRecognizer.call_count == 1

        stt.reset()
        assert mock_vosk.KaldiRecognizer.call_count == 2
