"""Wake word verification — energy-based false positive rejection."""


class WakeWordVerifier:
    """Verify wake word is from a real person, not from speakers."""

    def __init__(
        self,
        energy_ratio_threshold: float = 1.5,
        confidence_threshold: float = 0.8,
    ):
        self.energy_ratio_threshold = energy_ratio_threshold
        self.confidence_threshold = confidence_threshold

    def verify(
        self, mic_energy: float, loopback_energy: float, oww_confidence: float
    ) -> bool:
        """Verify wake word is from real person, not from speakers.

        Compares mic energy to loopback energy — if similar, the sound
        is likely coming from speakers (echo), not a real person.
        """
        energy_ratio = mic_energy / (loopback_energy + 1e-10)
        return (
            oww_confidence >= self.confidence_threshold
            and energy_ratio >= self.energy_ratio_threshold
        )
