"""Tests for EchoCanceller with mocked SpeexDSP."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from media_assistant.audio.aec import EchoCanceller


class TestEchoCancellerReducesReference:
    @patch("media_assistant.audio.aec.speexdsp")
    def test_echo_canceller_reduces_reference(self, mock_speexdsp):
        """mic = voice + echo → output should have echo reduced."""
        mock_ec = MagicMock()
        mock_speexdsp.EchoCanceller.create.return_value = mock_ec

        # Simulate AEC: when processing, return mic minus some of the reference
        def fake_process(mic_bytes, ref_bytes):
            mic = np.frombuffer(mic_bytes, dtype=np.int16)
            ref = np.frombuffer(ref_bytes, dtype=np.int16)
            # Simulate echo removal: subtract reference from mic
            clean = np.clip(mic.astype(np.int32) - ref.astype(np.int32), -32768, 32767)
            return clean.astype(np.int16).tobytes()

        mock_ec.process.side_effect = fake_process

        ec = EchoCanceller(frame_size=160, filter_length=1024, sample_rate=16000)

        # Create test signals: voice + echo in mic, echo as reference
        voice = np.full(512, 1000, dtype=np.int16)
        echo = np.full(512, 500, dtype=np.int16)
        mic_frame = np.clip(
            voice.astype(np.int32) + echo.astype(np.int32), -32768, 32767
        ).astype(np.int16)
        ref_frame = echo.copy()

        clean = ec.process(mic_frame, ref_frame)

        # Clean signal should be closer to voice than mic_frame was
        assert clean.dtype == np.int16
        assert len(clean) == 512
        # After AEC, the echo component should be reduced
        mic_echo_energy = np.mean((mic_frame.astype(float) - voice.astype(float)) ** 2)
        clean_echo_energy = np.mean((clean.astype(float) - voice.astype(float)) ** 2)
        assert clean_echo_energy < mic_echo_energy


class TestEchoCancellerPreservesVoice:
    @patch("media_assistant.audio.aec.speexdsp")
    def test_echo_canceller_preserves_voice(self, mock_speexdsp):
        """mic = pure voice, no echo → output ≈ input."""
        mock_ec = MagicMock()
        mock_speexdsp.EchoCanceller.create.return_value = mock_ec

        # When reference is silence, AEC should pass through
        def fake_process(mic_bytes, ref_bytes):
            return mic_bytes  # passthrough when no echo

        mock_ec.process.side_effect = fake_process

        ec = EchoCanceller(frame_size=160, filter_length=1024, sample_rate=16000)

        voice = np.array([500, -500] * 256, dtype=np.int16)  # 512 samples
        silence = np.zeros(512, dtype=np.int16)

        clean = ec.process(voice, silence)

        assert len(clean) == 512
        np.testing.assert_array_equal(clean, voice)


class TestEchoCancellerChunking:
    @patch("media_assistant.audio.aec.speexdsp")
    def test_process_chunks_512_into_160_subframes(self, mock_speexdsp):
        """512-sample frames should be chunked into 160-sample sub-frames for SpeexDSP."""
        mock_ec = MagicMock()
        mock_speexdsp.EchoCanceller.create.return_value = mock_ec

        # Track how many times the underlying SpeexDSP process is called
        def fake_process(mic_bytes, ref_bytes):
            return mic_bytes  # passthrough

        mock_ec.process.side_effect = fake_process

        ec = EchoCanceller(frame_size=160, filter_length=1024, sample_rate=16000)

        mic = np.ones(512, dtype=np.int16)
        ref = np.ones(512, dtype=np.int16)

        clean = ec.process(mic, ref)

        # 512 / 160 = 3 full chunks + 1 partial (32 samples) = 4 calls
        assert mock_ec.process.call_count == 4
        assert len(clean) == 512


class TestReset:
    @patch("media_assistant.audio.aec.speexdsp")
    def test_reset_recreates_internal_ec(self, mock_speexdsp):
        """Reset should create a fresh SpeexDSP EchoCanceller."""
        mock_ec1 = MagicMock()
        mock_ec2 = MagicMock()
        mock_speexdsp.EchoCanceller.create.side_effect = [mock_ec1, mock_ec2]

        ec = EchoCanceller(frame_size=160, filter_length=1024, sample_rate=16000)
        assert mock_speexdsp.EchoCanceller.create.call_count == 1

        ec.reset()
        assert mock_speexdsp.EchoCanceller.create.call_count == 2
