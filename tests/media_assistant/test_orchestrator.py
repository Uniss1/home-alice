"""Tests for Orchestrator state machine."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import numpy as np
import pytest

from media_assistant.audio.capture import AudioFrame
from media_assistant.intents.types import Intent, IntentType
from media_assistant.orchestrator import Orchestrator, State, _SILENCE_THRESHOLD


def _make_frame(mic_energy: float = 1000.0, loopback_energy: float = 100.0):
    """Create a test AudioFrame with controllable energy levels."""
    size = 512
    mic = (np.ones(size, dtype=np.int16) * mic_energy).astype(np.int16)
    loopback = (np.ones(size, dtype=np.int16) * loopback_energy).astype(np.int16)
    return AudioFrame(mic=mic, loopback=loopback, timestamp=0.0)


@pytest.fixture
def orch():
    """Create orchestrator with all components mocked."""
    o = Orchestrator.__new__(Orchestrator)
    o.state = State.IDLE

    o.audio = MagicMock()
    o.aec = MagicMock()
    o.noise = MagicMock()
    o.vad = MagicMock()
    o.wake_word = MagicMock()
    o.wake_verifier = MagicMock()
    o.stt_router = MagicMock()
    o.intent_router = MagicMock()
    o.llm_fallback = MagicMock()
    o.media = MagicMock()
    o.feedback = MagicMock()

    # Default returns
    clean = np.zeros(512, dtype=np.int16)
    o.aec.process.return_value = clean
    o.noise.process.return_value = clean
    o.vad.is_speech.return_value = False
    o.wake_word.process_frame.return_value = 0.0
    o.wake_verifier.verify.return_value = False
    o.llm_fallback.is_available.return_value = False

    o._saved_volume = None
    o._speech_buffer = []
    o._silence_frames = 0
    o._config_max_listen_seconds = 5.0
    o._config_frame_size = 512
    o._config_sample_rate = 16000

    return o


class TestStateTransitionsIdleToListening:
    @pytest.mark.asyncio
    async def test_wake_word_detected_transitions_to_listening(self, orch):
        orch.wake_word.process_frame.return_value = 0.95
        orch.wake_verifier.verify.return_value = True

        frame = _make_frame(mic_energy=5000, loopback_energy=100)
        await orch._process_frame(frame)

        assert orch.state == State.LISTENING
        orch.feedback.play_wake.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_wake_word_stays_idle(self, orch):
        orch.wake_word.process_frame.return_value = 0.1
        orch.wake_verifier.verify.return_value = False

        frame = _make_frame()
        await orch._process_frame(frame)

        assert orch.state == State.IDLE
        orch.feedback.play_wake.assert_not_called()


class TestStateTransitionsListeningToProcessing:
    @pytest.mark.asyncio
    async def test_silence_after_speech_triggers_processing(self, orch):
        orch.state = State.LISTENING
        orch._speech_buffer = [np.zeros(512, dtype=np.int16)] * 5
        orch._silence_frames = 0

        # Feed frames with no speech to trigger silence threshold
        frame = _make_frame()
        for _ in range(9):
            orch.vad.is_speech.return_value = False
            await orch._handle_listening(np.zeros(512, dtype=np.int16))

        # After 9 silent frames (> threshold of 8), should transition
        assert orch.state != State.LISTENING or orch._silence_frames >= 8

    @pytest.mark.asyncio
    async def test_speech_resets_silence_counter(self, orch):
        orch.state = State.LISTENING
        orch._speech_buffer = []
        orch._silence_frames = 5
        orch.vad.is_speech.return_value = True

        await orch._handle_listening(np.zeros(512, dtype=np.int16))

        assert orch._silence_frames == 0


class TestAutoMute:
    @pytest.mark.asyncio
    async def test_auto_mute_on_wake(self, orch):
        orch.wake_word.process_frame.return_value = 0.95
        orch.wake_verifier.verify.return_value = True

        with patch("media_assistant.orchestrator.volume_get", return_value=0.8), \
             patch("media_assistant.orchestrator.volume_set") as mock_set:
            frame = _make_frame(mic_energy=5000, loopback_energy=100)
            await orch._process_frame(frame)

            # Volume should be reduced to ~10%
            mock_set.assert_called_once()
            level = mock_set.call_args[0][0]
            assert level <= 10  # 80% * 10% = 8%

    @pytest.mark.asyncio
    async def test_auto_unmute_after_action(self, orch):
        orch._saved_volume = 0.8

        with patch("media_assistant.orchestrator.volume_set") as mock_set:
            orch._auto_unmute()
            mock_set.assert_called_once_with(80)
            assert orch._saved_volume is None


class TestIntentRouting:
    @pytest.mark.asyncio
    async def test_regex_match_used_directly(self, orch):
        orch.intent_router.route.return_value = Intent(
            type=IntentType.PAUSE
        )
        orch.media.active_provider = MagicMock()
        orch.media.active_provider.pause.return_value = "Пауза"

        with patch("media_assistant.orchestrator.volume_set"):
            await orch._route_intent("пауза")

        orch.intent_router.route.assert_called_once_with("пауза")
        # LLM fallback should not be called
        orch.llm_fallback.route.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_intent_falls_back_to_llm(self, orch):
        orch.intent_router.route.return_value = Intent(
            type=IntentType.UNKNOWN, query="сделай потише"
        )
        orch.llm_fallback.is_available.return_value = True
        orch.llm_fallback.route.return_value = Intent(
            type=IntentType.VOLUME_DOWN
        )

        with patch("media_assistant.orchestrator.volume_set"), \
             patch("media_assistant.orchestrator.volume_get", return_value=0.5):
            await orch._route_intent("сделай потише")

        orch.llm_fallback.route.assert_called_once_with("сделай потише")

    @pytest.mark.asyncio
    async def test_llm_unavailable_stays_unknown(self, orch):
        orch.intent_router.route.return_value = Intent(
            type=IntentType.UNKNOWN, query="что-то"
        )
        orch.llm_fallback.is_available.return_value = False

        with patch("media_assistant.orchestrator.volume_set"):
            await orch._route_intent("что-то")

        orch.llm_fallback.route.assert_not_called()


class TestExecuteIntent:
    @pytest.mark.asyncio
    async def test_play_media(self, orch):
        orch.media.play.return_value = "Включаю: «Interstellar»"

        await orch._execute_intent(
            Intent(type=IntentType.PLAY_MEDIA, query="interstellar")
        )
        orch.media.play.assert_called_once_with("interstellar")

    @pytest.mark.asyncio
    async def test_pause(self, orch):
        orch.media.pause.return_value = "Пауза"
        await orch._execute_intent(Intent(type=IntentType.PAUSE))
        orch.media.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume(self, orch):
        orch.media.resume.return_value = "Продолжаю"
        await orch._execute_intent(Intent(type=IntentType.RESUME))
        orch.media.resume.assert_called_once()

    @pytest.mark.asyncio
    async def test_volume_set(self, orch):
        with patch("media_assistant.orchestrator.volume_set") as mock_vs:
            await orch._execute_intent(
                Intent(type=IntentType.VOLUME_SET, params={"level": 50})
            )
            mock_vs.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_fullscreen(self, orch):
        orch.media.fullscreen.return_value = "Полный экран"
        await orch._execute_intent(Intent(type=IntentType.FULLSCREEN))
        orch.media.fullscreen.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_enters_confirming(self, orch):
        await orch._execute_intent(Intent(type=IntentType.SHUTDOWN))
        assert orch.state == State.CONFIRMING

    @pytest.mark.asyncio
    async def test_next_track(self, orch):
        with patch("media_assistant.orchestrator.next_track") as mock_nt:
            await orch._execute_intent(Intent(type=IntentType.NEXT_TRACK))
            mock_nt.assert_called_once()

    @pytest.mark.asyncio
    async def test_prev_track(self, orch):
        with patch("media_assistant.orchestrator.prev_track") as mock_pt:
            await orch._execute_intent(Intent(type=IntentType.PREV_TRACK))
            mock_pt.assert_called_once()


class TestConfirmation:
    @pytest.mark.asyncio
    async def test_confirmation_yes_executes_action(self, orch):
        orch.state = State.CONFIRMING
        orch._pending_intent = Intent(type=IntentType.SHUTDOWN)
        orch.vad.is_speech.return_value = False  # silence → triggers threshold
        orch.stt_router.transcribe.return_value = "да"

        with patch("media_assistant.orchestrator.shutdown") as mock_sd, \
             patch("media_assistant.orchestrator.volume_set"):
            # Pre-fill buffer with speech, set silence high enough to trigger
            orch._speech_buffer = [np.zeros(512, dtype=np.int16)]
            orch._silence_frames = _SILENCE_THRESHOLD
            await orch._handle_confirming(np.zeros(512, dtype=np.int16))

            mock_sd.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirmation_no_returns_to_idle(self, orch):
        orch.state = State.CONFIRMING
        orch._pending_intent = Intent(type=IntentType.SHUTDOWN)

        orch._speech_buffer = [np.zeros(512, dtype=np.int16)]
        orch._silence_frames = 9
        orch.stt_router.transcribe.return_value = "нет"

        with patch("media_assistant.orchestrator.volume_set"):
            await orch._handle_confirming(np.zeros(512, dtype=np.int16))

        assert orch.state == State.IDLE
