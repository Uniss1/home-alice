"""Echo cancellation via SpeexDSP adaptive filter."""

import numpy as np

try:
    import speexdsp
except ImportError:
    speexdsp = None  # type: ignore[assignment]  # Mocked in tests on non-Windows


class EchoCanceller:
    """Remove echo from microphone using loopback as reference signal.

    Handles chunking of larger frames into SpeexDSP's required frame_size.
    """

    def __init__(
        self,
        frame_size: int = 160,
        filter_length: int = 1024,
        sample_rate: int = 16000,
    ):
        self._frame_size = frame_size
        self._filter_length = filter_length
        self._sample_rate = sample_rate
        self._ec = speexdsp.EchoCanceller.create(
            frame_size, filter_length, sample_rate
        )

    def process(self, mic_frame: np.ndarray, ref_frame: np.ndarray) -> np.ndarray:
        """Cancel echo: mic - reference -> clean signal.

        Chunks input into frame_size sub-frames for SpeexDSP processing.
        """
        total = len(mic_frame)
        output = np.empty(total, dtype=np.int16)
        pos = 0

        while pos < total:
            end = min(pos + self._frame_size, total)
            chunk_mic = mic_frame[pos:end]
            chunk_ref = ref_frame[pos:end]

            clean_bytes = self._ec.process(
                chunk_mic.tobytes(), chunk_ref.tobytes()
            )
            clean = np.frombuffer(clean_bytes, dtype=np.int16)
            output[pos : pos + len(clean)] = clean
            pos = end

        return output

    def reset(self) -> None:
        """Reset adaptive filter state by recreating the internal EC."""
        self._ec = speexdsp.EchoCanceller.create(
            self._frame_size, self._filter_length, self._sample_rate
        )
