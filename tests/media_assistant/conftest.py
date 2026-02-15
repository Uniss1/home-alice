"""Shared fixtures for media_assistant integration tests."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from media_assistant.audio.capture import AudioFrame
from media_assistant.intents.regex_router import RegexIntentRouter
from media_assistant.intents.types import Intent, IntentType
from media_assistant.orchestrator import Orchestrator, State, _SILENCE_THRESHOLD


def make_frame(mic_energy: float = 1000.0, loopback_energy: float = 100.0, size: int = 512):
    """Create a test AudioFrame with controllable energy levels."""
    mic = (np.ones(size, dtype=np.int16) * mic_energy).astype(np.int16)
    loopback = (np.ones(size, dtype=np.int16) * loopback_energy).astype(np.int16)
    return AudioFrame(mic=mic, loopback=loopback, timestamp=0.0)


@pytest.fixture
def integration_orch():
    """Orchestrator with real RegexIntentRouter but mocked I/O components.

    This tests the full pipeline: audio processing → wake word → STT → intent → action,
    with only external I/O mocked (audio capture, STT engines, media, volume, system).
    """
    o = Orchestrator.__new__(Orchestrator)
    o.state = State.IDLE

    # Mocked I/O components
    o.audio = MagicMock()
    o.aec = MagicMock()
    o.noise = MagicMock()
    o.vad = MagicMock()
    o.wake_word = MagicMock()
    o.wake_verifier = MagicMock()
    o.stt_router = MagicMock()
    o.llm_fallback = MagicMock()
    o.media = MagicMock()
    o.feedback = MagicMock()

    # Real intent router — tests the actual regex matching
    o.intent_router = RegexIntentRouter()

    # Default behaviour: passthrough audio, no wake word, no speech
    clean = np.zeros(512, dtype=np.int16)
    o.aec.process.return_value = clean
    o.noise.process.return_value = clean
    o.vad.is_speech.return_value = False
    o.wake_word.process_frame.return_value = 0.0
    o.wake_verifier.verify.return_value = False
    o.llm_fallback.is_available.return_value = False

    # Internal state
    o._saved_volume = None
    o._speech_buffer = []
    o._silence_frames = 0
    o._pending_intent = None
    o._config_max_listen_seconds = 5.0
    o._config_frame_size = 512
    o._config_sample_rate = 16000

    return o


async def simulate_wake(orch):
    """Trigger wake word detection on the orchestrator."""
    orch.wake_word.process_frame.return_value = 0.95
    orch.wake_verifier.verify.return_value = True

    frame = make_frame(mic_energy=5000, loopback_energy=100)
    with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
         patch("media_assistant.orchestrator.volume_set"):
        await orch._process_frame(frame)

    assert orch.state == State.LISTENING

    # Reset wake word so further frames don't re-trigger
    orch.wake_word.process_frame.return_value = 0.0
    orch.wake_verifier.verify.return_value = False


async def simulate_speech_then_silence(orch, stt_text: str):
    """Feed speech frames followed by silence to trigger STT processing.

    Sets up the STT mock to return stt_text, then feeds enough silence frames
    to cross the threshold.

    IMPORTANT: Caller must patch volume_get/volume_set if auto_unmute might fire.
    """
    orch.stt_router.transcribe.return_value = stt_text

    # Feed a few speech frames
    orch.vad.is_speech.return_value = True
    for _ in range(3):
        await orch._handle_listening(np.zeros(512, dtype=np.int16))

    # Feed silence frames to trigger processing
    orch.vad.is_speech.return_value = False
    for _ in range(_SILENCE_THRESHOLD + 1):
        if orch.state == State.LISTENING:
            await orch._handle_listening(np.zeros(512, dtype=np.int16))
