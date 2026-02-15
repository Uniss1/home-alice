"""Tests for VoiceActivityDetector with mocked Silero VAD."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.audio.vad import VoiceActivityDetector


class TestVADDetectsSpeech:
    @patch("media_assistant.audio.vad.torch")
    def test_vad_detects_speech(self, mock_torch):
        """Frame with speech → True."""
        mock_model = MagicMock()
        mock_torch.hub.load.return_value = (mock_model, None)

        # Model returns high confidence for speech
        mock_model.return_value = MagicMock(item=MagicMock(return_value=0.9))

        vad = VoiceActivityDetector(threshold=0.5)

        speech = np.random.randint(-5000, 5000, 512, dtype=np.int16)
        assert vad.is_speech(speech) is True


class TestVADRejectsSilence:
    @patch("media_assistant.audio.vad.torch")
    def test_vad_rejects_silence(self, mock_torch):
        """Silent frame → False."""
        mock_model = MagicMock()
        mock_torch.hub.load.return_value = (mock_model, None)

        # Model returns low confidence for silence
        mock_model.return_value = MagicMock(item=MagicMock(return_value=0.05))

        vad = VoiceActivityDetector(threshold=0.5)

        silence = np.zeros(512, dtype=np.int16)
        assert vad.is_speech(silence) is False


class TestVADRejectsNoise:
    @patch("media_assistant.audio.vad.torch")
    def test_vad_rejects_noise(self, mock_torch):
        """Noise-only frame → False."""
        mock_model = MagicMock()
        mock_torch.hub.load.return_value = (mock_model, None)

        # Model returns below-threshold for noise
        mock_model.return_value = MagicMock(item=MagicMock(return_value=0.3))

        vad = VoiceActivityDetector(threshold=0.5)

        noise = np.random.randint(-100, 100, 512, dtype=np.int16)
        assert vad.is_speech(noise) is False


class TestVADReset:
    @patch("media_assistant.audio.vad.torch")
    def test_reset_clears_model_state(self, mock_torch):
        """Reset should call model.reset_states()."""
        mock_model = MagicMock()
        mock_torch.hub.load.return_value = (mock_model, None)

        vad = VoiceActivityDetector(threshold=0.5)
        vad.reset()

        mock_model.reset_states.assert_called_once()
