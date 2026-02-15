"""Tests for sound feedback system."""

from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from media_assistant.feedback.sounds import SoundFeedback


@pytest.fixture
def feedback():
    return SoundFeedback()


class TestGenerateBeep:
    def test_wake_beep_shape(self, feedback):
        assert feedback._wake_beep.dtype == np.int16
        expected_len = int(16000 * 0.05)
        assert len(feedback._wake_beep) == expected_len

    def test_confirm_beep_shape(self, feedback):
        assert feedback._confirm_beep.dtype == np.int16
        expected_len = int(16000 * 0.1)
        assert len(feedback._confirm_beep) == expected_len

    def test_error_beep_shape(self, feedback):
        assert feedback._error_beep.dtype == np.int16
        expected_len = int(16000 * 0.2)
        assert len(feedback._error_beep) == expected_len

    def test_beep_values_in_int16_range(self, feedback):
        for beep in [feedback._wake_beep, feedback._confirm_beep, feedback._error_beep]:
            assert beep.max() <= 32767
            assert beep.min() >= -32768

    def test_beep_not_silent(self, feedback):
        # Beeps should have non-zero amplitude
        for beep in [feedback._wake_beep, feedback._confirm_beep, feedback._error_beep]:
            assert np.abs(beep).max() > 0


class TestPlayWake:
    @patch("media_assistant.feedback.sounds.sd")
    def test_play_wake_calls_sounddevice(self, mock_sd, feedback):
        feedback.play_wake()
        mock_sd.play.assert_called_once()
        args = mock_sd.play.call_args
        np.testing.assert_array_equal(args[0][0], feedback._wake_beep)
        assert args[0][1] == 16000


class TestPlaySearching:
    @patch("media_assistant.feedback.sounds.sd")
    def test_play_searching_calls_sounddevice(self, mock_sd, feedback):
        feedback.play_searching()
        mock_sd.play.assert_called_once()
        args = mock_sd.play.call_args
        np.testing.assert_array_equal(args[0][0], feedback._confirm_beep)


class TestPlayError:
    @patch("media_assistant.feedback.sounds.sd")
    def test_play_error_calls_sounddevice(self, mock_sd, feedback):
        feedback.play_error()
        mock_sd.play.assert_called_once()
        args = mock_sd.play.call_args
        np.testing.assert_array_equal(args[0][0], feedback._error_beep)


class TestCustomSampleRate:
    def test_custom_sample_rate(self):
        fb = SoundFeedback(sample_rate=8000)
        expected_len = int(8000 * 0.05)
        assert len(fb._wake_beep) == expected_len
