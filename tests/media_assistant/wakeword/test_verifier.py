"""Tests for WakeWordVerifier — energy-based false positive rejection."""

import pytest

from media_assistant.wakeword.verifier import WakeWordVerifier


class TestVerifierAcceptsRealVoice:
    def test_accepts_real_voice(self):
        """mic_energy >> loopback_energy, high confidence → True."""
        verifier = WakeWordVerifier(
            energy_ratio_threshold=1.5, confidence_threshold=0.8
        )
        # Mic much louder than loopback → real person speaking
        assert verifier.verify(mic_energy=500.0, loopback_energy=100.0, oww_confidence=0.95) is True


class TestVerifierRejectsSpeakerEcho:
    def test_rejects_speaker_echo(self):
        """mic_energy ≈ loopback_energy → False (sound from speakers)."""
        verifier = WakeWordVerifier(
            energy_ratio_threshold=1.5, confidence_threshold=0.8
        )
        # Mic and loopback similar → sound from speakers, not real person
        assert verifier.verify(mic_energy=100.0, loopback_energy=100.0, oww_confidence=0.95) is False


class TestVerifierRejectsLowConfidence:
    def test_rejects_low_confidence(self):
        """High energy ratio but low confidence → False."""
        verifier = WakeWordVerifier(
            energy_ratio_threshold=1.5, confidence_threshold=0.8
        )
        # Real voice (high ratio) but OWW not confident → False
        assert verifier.verify(mic_energy=500.0, loopback_energy=100.0, oww_confidence=0.5) is False


class TestVerifierEdgeCases:
    def test_zero_loopback_energy(self):
        """Zero loopback energy should not crash (division by zero protected)."""
        verifier = WakeWordVerifier()
        assert verifier.verify(mic_energy=500.0, loopback_energy=0.0, oww_confidence=0.9) is True

    def test_exact_threshold_values(self):
        """Exactly at threshold → should pass (>= check)."""
        verifier = WakeWordVerifier(
            energy_ratio_threshold=1.5, confidence_threshold=0.8
        )
        # Just above thresholds
        assert verifier.verify(mic_energy=1.51, loopback_energy=1.0, oww_confidence=0.81) is True
        # Just below energy threshold
        assert verifier.verify(mic_energy=1.49, loopback_energy=1.0, oww_confidence=0.81) is False
        # Just below confidence threshold
        assert verifier.verify(mic_energy=1.51, loopback_energy=1.0, oww_confidence=0.79) is False
