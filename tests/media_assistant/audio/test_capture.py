"""Tests for AudioCapture with mocked PyAudioWPatch."""

import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest

from media_assistant.audio.capture import AudioCapture, AudioFrame


class TestAudioFrame:
    def test_audio_frame_holds_mic_loopback_timestamp(self):
        mic = np.zeros(512, dtype=np.int16)
        loopback = np.zeros(512, dtype=np.int16)
        ts = 1234567890.0
        frame = AudioFrame(mic=mic, loopback=loopback, timestamp=ts)
        assert frame.mic is mic
        assert frame.loopback is loopback
        assert frame.timestamp == ts


class TestAudioCaptureStartStop:
    @patch("media_assistant.audio.capture.pyaudio")
    def test_start_opens_mic_and_loopback_streams(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa

        # Mock WASAPI loopback device
        mock_loopback_device = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 48000.0,
            "maxInputChannels": 2,
        }
        mock_pa.get_wasapi_loopback.return_value = mock_loopback_device

        capture = AudioCapture(sample_rate=16000, frame_size=512)
        capture.start()

        # Should open two streams: mic + loopback
        assert mock_pa.open.call_count == 2

        capture.stop()
        assert not capture.is_running

    @patch("media_assistant.audio.capture.pyaudio")
    def test_stop_closes_streams_and_terminates(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa

        mock_loopback_device = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 48000.0,
            "maxInputChannels": 2,
        }
        mock_pa.get_wasapi_loopback.return_value = mock_loopback_device

        mock_mic_stream = MagicMock()
        mock_loopback_stream = MagicMock()
        mock_pa.open.side_effect = [mock_mic_stream, mock_loopback_stream]

        capture = AudioCapture(sample_rate=16000, frame_size=512)
        capture.start()
        capture.stop()

        mock_mic_stream.stop_stream.assert_called_once()
        mock_mic_stream.close.assert_called_once()
        mock_loopback_stream.stop_stream.assert_called_once()
        mock_loopback_stream.close.assert_called_once()
        mock_pa.terminate.assert_called_once()

    @patch("media_assistant.audio.capture.pyaudio")
    def test_is_running_reflects_state(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pa.get_wasapi_loopback.return_value = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 48000.0,
            "maxInputChannels": 2,
        }

        capture = AudioCapture()
        assert not capture.is_running

        capture.start()
        assert capture.is_running

        capture.stop()
        assert not capture.is_running


class TestReadFrame:
    @patch("media_assistant.audio.capture.pyaudio")
    def test_read_frame_returns_synchronized_data(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pa.get_wasapi_loopback.return_value = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 16000.0,
            "maxInputChannels": 1,
        }

        # Prepare mic and loopback data (mono 16kHz int16)
        mic_data = np.ones(512, dtype=np.int16) * 100
        loopback_data = np.ones(512, dtype=np.int16) * 200

        mic_bytes = mic_data.tobytes()
        loopback_bytes = loopback_data.tobytes()

        mock_mic_stream = MagicMock()
        mock_loopback_stream = MagicMock()

        mock_mic_stream.read.return_value = mic_bytes
        mock_loopback_stream.read.return_value = loopback_bytes

        mock_pa.open.side_effect = [mock_mic_stream, mock_loopback_stream]

        capture = AudioCapture(sample_rate=16000, frame_size=512)
        capture.start()

        # Give callback threads time to process
        time.sleep(0.2)

        frame = capture.read_frame(timeout=1.0)
        assert frame is not None
        assert isinstance(frame, AudioFrame)
        assert len(frame.mic) == 512
        assert len(frame.loopback) == 512
        assert frame.timestamp > 0
        np.testing.assert_array_equal(frame.mic, mic_data)
        np.testing.assert_array_equal(frame.loopback, loopback_data)

        capture.stop()

    @patch("media_assistant.audio.capture.pyaudio")
    def test_read_frame_timeout_returns_none(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa
        mock_pa.get_wasapi_loopback.return_value = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 16000.0,
            "maxInputChannels": 1,
        }

        # Streams that never produce data
        mock_mic_stream = MagicMock()
        mock_loopback_stream = MagicMock()
        mock_mic_stream.read.side_effect = lambda *a, **kw: time.sleep(10)
        mock_loopback_stream.read.side_effect = lambda *a, **kw: time.sleep(10)
        mock_pa.open.side_effect = [mock_mic_stream, mock_loopback_stream]

        capture = AudioCapture(sample_rate=16000, frame_size=512)
        capture.start()

        frame = capture.read_frame(timeout=0.1)
        assert frame is None

        capture.stop()


class TestLoopbackResampling:
    @patch("media_assistant.audio.capture.pyaudio")
    def test_loopback_resampled_to_mono_16khz(self, mock_pyaudio):
        mock_pa = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_pa

        # Loopback device is stereo 48kHz
        mock_pa.get_wasapi_loopback.return_value = {
            "index": 5,
            "name": "Speakers (loopback)",
            "defaultSampleRate": 48000.0,
            "maxInputChannels": 2,
        }

        # Stereo 48kHz data: frame_size * (48000/16000) * 2 channels = 512 * 3 * 2 = 3072 samples
        stereo_48k = np.ones(3072, dtype=np.int16) * 300
        stereo_48k_bytes = stereo_48k.tobytes()

        mic_data = np.ones(512, dtype=np.int16) * 100
        mic_bytes = mic_data.tobytes()

        mock_mic_stream = MagicMock()
        mock_loopback_stream = MagicMock()
        mock_mic_stream.read.return_value = mic_bytes
        mock_loopback_stream.read.return_value = stereo_48k_bytes

        mock_pa.open.side_effect = [mock_mic_stream, mock_loopback_stream]

        capture = AudioCapture(sample_rate=16000, frame_size=512)
        capture.start()

        time.sleep(0.2)

        frame = capture.read_frame(timeout=1.0)
        assert frame is not None
        # Output should be mono 16kHz → 512 samples
        assert len(frame.loopback) == 512
        assert frame.loopback.dtype == np.int16

        capture.stop()
