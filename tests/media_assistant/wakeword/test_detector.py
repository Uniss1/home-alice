"""Tests for WakeWordDetector with mocked OpenWakeWord."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.wakeword.detector import WakeWordDetector


class TestDetectorReturnsConfidence:
    @patch("media_assistant.wakeword.detector.openwakeword")
    def test_process_frame_returns_float_confidence(self, mock_oww):
        """process_frame should return a float between 0.0 and 1.0."""
        mock_model = MagicMock()
        mock_oww.Model.return_value = mock_model

        # OpenWakeWord returns dict of model_name -> score
        mock_model.predict.return_value = {"jarvis": 0.75}

        detector = WakeWordDetector(model_path="jarvis.onnx", threshold=0.8)
        frame = np.random.randint(-1000, 1000, 512, dtype=np.int16)

        confidence = detector.process_frame(frame)

        assert isinstance(confidence, float)
        assert confidence == 0.75


class TestDetectorThreshold:
    @patch("media_assistant.wakeword.detector.openwakeword")
    def test_detected_true_above_threshold(self, mock_oww):
        """confidence > threshold → detected=True."""
        mock_model = MagicMock()
        mock_oww.Model.return_value = mock_model
        mock_model.predict.return_value = {"jarvis": 0.9}

        detector = WakeWordDetector(model_path="jarvis.onnx", threshold=0.8)
        frame = np.zeros(512, dtype=np.int16)

        assert detector.detected(frame) is True

    @patch("media_assistant.wakeword.detector.openwakeword")
    def test_detected_false_below_threshold(self, mock_oww):
        """confidence < threshold → detected=False."""
        mock_model = MagicMock()
        mock_oww.Model.return_value = mock_model
        mock_model.predict.return_value = {"jarvis": 0.5}

        detector = WakeWordDetector(model_path="jarvis.onnx", threshold=0.8)
        frame = np.zeros(512, dtype=np.int16)

        assert detector.detected(frame) is False


class TestDetectorReset:
    @patch("media_assistant.wakeword.detector.openwakeword")
    def test_reset_calls_model_reset(self, mock_oww):
        """Reset should call model.reset()."""
        mock_model = MagicMock()
        mock_oww.Model.return_value = mock_model

        detector = WakeWordDetector(model_path="jarvis.onnx")
        detector.reset()

        mock_model.reset.assert_called_once()
