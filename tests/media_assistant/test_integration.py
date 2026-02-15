"""Integration tests — full pipeline E2E with mocked audio."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from media_assistant.intents.types import Intent, IntentType
from media_assistant.orchestrator import State, _SILENCE_THRESHOLD
from tests.media_assistant.conftest import make_frame, simulate_wake, simulate_speech_then_silence


class TestE2EWakeWordToPlayMedia:
    """Full pipeline: wake word → STT → intent → play video."""

    @pytest.mark.asyncio
    async def test_wake_stt_intent_play(self, integration_orch):
        orch = integration_orch

        # Step 1: Wake word detected → LISTENING
        await simulate_wake(orch)
        assert orch.state == State.LISTENING
        orch.feedback.play_wake.assert_called_once()

        # Step 2: Speech "включи интерстеллар" → STT → regex → PLAY_MEDIA
        orch.media.play.return_value = "Включаю: «Interstellar»"

        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await simulate_speech_then_silence(orch, "включи интерстеллар")

        # Step 3: Verify media.play called with correct query
        orch.media.play.assert_called_once_with("интерстеллар")
        orch.feedback.play_searching.assert_called_once()
        assert orch.state == State.IDLE


class TestE2EPauseResume:
    """Wake → "пауза" → paused. Wake → "продолжи" → resumed."""

    @pytest.mark.asyncio
    async def test_pause(self, integration_orch):
        orch = integration_orch
        orch.media.pause.return_value = "Пауза"

        await simulate_wake(orch)
        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await simulate_speech_then_silence(orch, "пауза")

        orch.media.pause.assert_called_once()
        assert orch.state == State.IDLE

    @pytest.mark.asyncio
    async def test_resume(self, integration_orch):
        orch = integration_orch
        orch.media.resume.return_value = "Продолжаю"

        await simulate_wake(orch)
        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await simulate_speech_then_silence(orch, "продолжи")

        orch.media.resume.assert_called_once()
        assert orch.state == State.IDLE


class TestE2EVolumeControl:
    """Wake → "громкость 50" → volume set to 50%."""

    @pytest.mark.asyncio
    async def test_volume_set_50(self, integration_orch):
        orch = integration_orch

        await simulate_wake(orch)
        # Override saved volume so auto_unmute (80) is distinguishable from command (50)
        orch._saved_volume = 0.8

        with patch("media_assistant.orchestrator.volume_get", return_value=0.8), \
             patch("media_assistant.orchestrator.volume_set") as mock_vs:
            await simulate_speech_then_silence(orch, "громкость 50")

            # volume_set called for the command (50) and auto_unmute (80)
            calls_50 = [c for c in mock_vs.call_args_list if c[0] == (50,)]
            calls_80 = [c for c in mock_vs.call_args_list if c[0] == (80,)]
            assert len(calls_50) == 1  # the volume command
            assert len(calls_80) == 1  # auto_unmute restoring saved volume

        assert orch.state == State.IDLE


class TestE2EShutdownConfirmation:
    """Wake → "выключи компьютер" → CONFIRMING → "да" → shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_confirmed(self, integration_orch):
        orch = integration_orch

        # Step 1: Wake → "выключи компьютер" → CONFIRMING
        await simulate_wake(orch)
        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await simulate_speech_then_silence(orch, "выключи компьютер")

        assert orch.state == State.CONFIRMING
        assert orch._pending_intent is not None
        assert orch._pending_intent.type == IntentType.SHUTDOWN

        # Step 2: User says "да" → shutdown called
        orch.stt_router.transcribe.return_value = "да"

        # Feed speech then silence for confirmation
        orch.vad.is_speech.return_value = True
        for _ in range(2):
            await orch._handle_confirming(np.zeros(512, dtype=np.int16))

        orch.vad.is_speech.return_value = False
        with patch("media_assistant.orchestrator.shutdown") as mock_shutdown, \
             patch("media_assistant.orchestrator.volume_set"):
            for _ in range(_SILENCE_THRESHOLD + 1):
                if orch.state == State.CONFIRMING:
                    await orch._handle_confirming(np.zeros(512, dtype=np.int16))

            mock_shutdown.assert_called_once()

        assert orch.state == State.IDLE


class TestE2EShutdownRejection:
    """Wake → "выключи компьютер" → CONFIRMING → "нет" → back to IDLE."""

    @pytest.mark.asyncio
    async def test_shutdown_rejected(self, integration_orch):
        orch = integration_orch

        # Step 1: Wake → "выключи компьютер" → CONFIRMING
        await simulate_wake(orch)
        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await simulate_speech_then_silence(orch, "выключи компьютер")

        assert orch.state == State.CONFIRMING

        # Step 2: User says "нет" → back to IDLE, no shutdown
        orch.stt_router.transcribe.return_value = "нет"

        orch.vad.is_speech.return_value = True
        for _ in range(2):
            await orch._handle_confirming(np.zeros(512, dtype=np.int16))

        orch.vad.is_speech.return_value = False
        with patch("media_assistant.orchestrator.shutdown") as mock_shutdown, \
             patch("media_assistant.orchestrator.volume_set"):
            for _ in range(_SILENCE_THRESHOLD + 1):
                if orch.state == State.CONFIRMING:
                    await orch._handle_confirming(np.zeros(512, dtype=np.int16))

            mock_shutdown.assert_not_called()

        assert orch.state == State.IDLE


class TestE2EUnknownIntentLLMFallback:
    """Wake → unrecognized phrase → LLM fallback → correct intent."""

    @pytest.mark.asyncio
    async def test_llm_fallback_routes_correctly(self, integration_orch):
        orch = integration_orch

        # LLM fallback is available and returns VOLUME_DOWN
        orch.llm_fallback.is_available.return_value = True
        orch.llm_fallback.route.return_value = Intent(type=IntentType.VOLUME_DOWN)

        await simulate_wake(orch)
        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set") as mock_vs:
            await simulate_speech_then_silence(orch, "сделай потише")

            # Regex router returns UNKNOWN for "сделай потише", so LLM fallback kicks in
            orch.llm_fallback.route.assert_called_once_with("сделай потише")

        assert orch.state == State.IDLE


class TestE2EAECFiltersEcho:
    """Playing audio + voice command → AEC removes echo → correct STT."""

    @pytest.mark.asyncio
    async def test_aec_processes_mic_and_loopback(self, integration_orch):
        orch = integration_orch

        # Simulate playing video: high loopback energy (music/video audio)
        high_loopback = make_frame(mic_energy=5000, loopback_energy=3000)

        # AEC should receive both mic and loopback for echo cancellation
        clean_signal = np.zeros(512, dtype=np.int16)
        orch.aec.process.return_value = clean_signal
        orch.noise.process.return_value = clean_signal

        # Wake word detected even with high loopback (verifier checks energy ratio)
        orch.wake_word.process_frame.return_value = 0.95
        orch.wake_verifier.verify.return_value = True

        with patch("media_assistant.orchestrator.volume_get", return_value=0.5), \
             patch("media_assistant.orchestrator.volume_set"):
            await orch._process_frame(high_loopback)

        # Verify AEC received both mic and loopback for echo removal
        orch.aec.process.assert_called_once()
        call_args = orch.aec.process.call_args[0]
        np.testing.assert_array_equal(call_args[0], high_loopback.mic)
        np.testing.assert_array_equal(call_args[1], high_loopback.loopback)

        # After AEC, noise suppressor gets the clean signal
        orch.noise.process.assert_called_once_with(clean_signal)

        assert orch.state == State.LISTENING
