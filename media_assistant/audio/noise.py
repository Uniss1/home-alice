"""Noise suppression via DeepFilterNet."""

import numpy as np

try:
    from df import enhance as df_mod
except ImportError:
    df_mod = None  # type: ignore[assignment]  # Mocked in tests on non-Windows


class NoiseSuppressor:
    """Suppress background noise from audio frames using DeepFilterNet."""

    def __init__(self):
        model, df_state, sr = df_mod.init_df()
        self._model = model
        self._df_state = df_state
        self._sample_rate = sr

    def process(self, frame: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Suppress noise, return clean frame as int16."""
        audio_float = frame.astype(np.float32) / 32768.0
        clean_float = df_mod.enhance(self._model, self._df_state, audio_float)
        clean = np.clip(clean_float * 32768.0, -32768, 32767).astype(np.int16)
        return clean
