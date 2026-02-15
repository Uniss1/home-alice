"""Tests for NoiseSuppressor with mocked DeepFilterNet."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.audio.noise import NoiseSuppressor


class TestNoiseSuppressorReducesNoise:
    @patch("media_assistant.audio.noise.df_mod")
    def test_noise_suppressor_reduces_noise(self, mock_df):
        """Noisy signal → output has lower noise floor."""
        mock_model = MagicMock()
        mock_df_state = MagicMock()
        mock_df.init_df.return_value = (mock_model, mock_df_state, 16000)

        # Simulate noise reduction: attenuate by 50%
        def fake_enhance(model, df_state, audio):
            return audio * 0.5

        mock_df.enhance.side_effect = fake_enhance

        ns = NoiseSuppressor()

        noisy = np.random.randint(-1000, 1000, 512, dtype=np.int16)
        clean = ns.process(noisy)

        assert clean.dtype == np.int16
        assert len(clean) == 512
        # Output energy should be lower than input
        input_energy = np.mean(noisy.astype(float) ** 2)
        output_energy = np.mean(clean.astype(float) ** 2)
        assert output_energy < input_energy


class TestNoiseSuppressorPassesSilence:
    @patch("media_assistant.audio.noise.df_mod")
    def test_silence_stays_silent(self, mock_df):
        """Silent input → silent output."""
        mock_model = MagicMock()
        mock_df_state = MagicMock()
        mock_df.init_df.return_value = (mock_model, mock_df_state, 16000)

        def fake_enhance(model, df_state, audio):
            return audio  # passthrough

        mock_df.enhance.side_effect = fake_enhance

        ns = NoiseSuppressor()

        silence = np.zeros(512, dtype=np.int16)
        clean = ns.process(silence)

        np.testing.assert_array_equal(clean, silence)
