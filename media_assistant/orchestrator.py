"""Orchestrator — state machine connecting all media assistant components."""

import asyncio
import logging
from enum import Enum

import numpy as np

from media_assistant.audio.capture import AudioCapture, AudioFrame
from media_assistant.audio.aec import EchoCanceller
from media_assistant.audio.noise import NoiseSuppressor
from media_assistant.audio.vad import VoiceActivityDetector
from media_assistant.wakeword.detector import WakeWordDetector
from media_assistant.wakeword.verifier import WakeWordVerifier
from media_assistant.stt.router import STTRouter
from media_assistant.intents.types import Intent, IntentType
from media_assistant.intents.regex_router import RegexIntentRouter
from media_assistant.intents.llm_fallback import LLMFallbackRouter
from media_assistant.media.manager import MediaManager
from media_assistant.feedback.sounds import SoundFeedback

try:
    from shared.volume import volume_set, volume_get
except ImportError:
    volume_set = None  # type: ignore[assignment]
    volume_get = None  # type: ignore[assignment]

try:
    from media_assistant.control.media_keys import next_track, prev_track
except ImportError:
    next_track = None  # type: ignore[assignment]
    prev_track = None  # type: ignore[assignment]

try:
    from shared.system import shutdown, reboot
except ImportError:
    shutdown = None  # type: ignore[assignment]
    reboot = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Silence threshold: number of consecutive non-speech frames to end utterance
_SILENCE_THRESHOLD = 8


class State(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"
    CONFIRMING = "confirming"


class Orchestrator:
    def __init__(
        self,
        audio: AudioCapture,
        aec: EchoCanceller,
        noise: NoiseSuppressor,
        vad: VoiceActivityDetector,
        wake_word: WakeWordDetector,
        wake_verifier: WakeWordVerifier,
        stt_router: STTRouter,
        intent_router: RegexIntentRouter,
        llm_fallback: LLMFallbackRouter,
        media: MediaManager,
        feedback: SoundFeedback,
        max_listen_seconds: float = 5.0,
        frame_size: int = 512,
        sample_rate: int = 16000,
    ):
        self.state = State.IDLE

        self.audio = audio
        self.aec = aec
        self.noise = noise
        self.vad = vad
        self.wake_word = wake_word
        self.wake_verifier = wake_verifier
        self.stt_router = stt_router
        self.intent_router = intent_router
        self.llm_fallback = llm_fallback
        self.media = media
        self.feedback = feedback

        self._config_max_listen_seconds = max_listen_seconds
        self._config_frame_size = frame_size
        self._config_sample_rate = sample_rate

        self._saved_volume: float | None = None
        self._speech_buffer: list[np.ndarray] = []
        self._silence_frames: int = 0
        self._pending_intent: Intent | None = None

    async def run(self) -> None:
        """Main event loop."""
        self.audio.start()
        try:
            while True:
                frame = self.audio.read_frame()
                if frame is None:
                    await asyncio.sleep(0.01)
                    continue
                await self._process_frame(frame)
        finally:
            self.audio.stop()

    async def _process_frame(self, frame: AudioFrame) -> None:
        clean = self.aec.process(frame.mic, frame.loopback)
        clean = self.noise.process(clean)

        if self.state == State.IDLE:
            await self._handle_idle(clean, frame)
        elif self.state == State.LISTENING:
            await self._handle_listening(clean)
        elif self.state == State.CONFIRMING:
            await self._handle_confirming(clean)

    async def _handle_idle(self, clean: np.ndarray, frame: AudioFrame) -> None:
        confidence = self.wake_word.process_frame(clean)
        mic_energy = float(np.sqrt(np.mean(frame.mic.astype(float) ** 2)))
        loopback_energy = float(np.sqrt(np.mean(frame.loopback.astype(float) ** 2)))

        if self.wake_verifier.verify(mic_energy, loopback_energy, confidence):
            self.feedback.play_wake()
            self._auto_mute()
            self.state = State.LISTENING
            self._speech_buffer = []
            self._silence_frames = 0

    async def _handle_listening(self, clean: np.ndarray) -> None:
        self._speech_buffer.append(clean)

        if self.vad.is_speech(clean):
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        total_seconds = (
            len(self._speech_buffer) * self._config_frame_size / self._config_sample_rate
        )
        if self._silence_frames > _SILENCE_THRESHOLD or total_seconds > self._config_max_listen_seconds:
            self.state = State.PROCESSING
            audio = np.concatenate(self._speech_buffer)
            text = self.stt_router.transcribe(audio, context="general")
            await self._route_intent(text)

    async def _handle_confirming(self, clean: np.ndarray) -> None:
        self._speech_buffer.append(clean)

        if self.vad.is_speech(clean):
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        if self._silence_frames > _SILENCE_THRESHOLD:
            audio = np.concatenate(self._speech_buffer)
            text = self.stt_router.transcribe(audio, context="confirmation")
            text_lower = text.lower().strip()

            if text_lower in ("да", "подтверждаю", "выключай"):
                await self._execute_confirmed(self._pending_intent)
            # Any other response (including "нет") → return to idle
            self._pending_intent = None
            self._auto_unmute()
            self.state = State.IDLE

    async def _route_intent(self, text: str) -> None:
        self.feedback.play_searching()
        intent = self.intent_router.route(text)

        if intent.type == IntentType.UNKNOWN and self.llm_fallback.is_available():
            intent = self.llm_fallback.route(text)

        self.state = State.RESPONDING
        await self._execute_intent(intent)

        # Return to idle unless waiting for confirmation
        if self.state != State.CONFIRMING:
            self._auto_unmute()
            self.state = State.IDLE

    async def _execute_intent(self, intent: Intent) -> None:
        match intent.type:
            case IntentType.PLAY_MEDIA:
                self.media.play(intent.query)
            case IntentType.PAUSE:
                self.media.pause()
            case IntentType.RESUME:
                self.media.resume()
            case IntentType.FULLSCREEN:
                self.media.fullscreen()
            case IntentType.VOLUME_SET:
                volume_set(intent.params["level"])
            case IntentType.VOLUME_UP:
                current = volume_get()
                volume_set(min(100, int(current * 100) + 10))
            case IntentType.VOLUME_DOWN:
                current = volume_get()
                volume_set(max(0, int(current * 100) - 10))
            case IntentType.NEXT_TRACK:
                next_track()
            case IntentType.PREV_TRACK:
                prev_track()
            case IntentType.SHUTDOWN:
                self.state = State.CONFIRMING
                self._pending_intent = intent
                self._speech_buffer = []
                self._silence_frames = 0
            case IntentType.REBOOT:
                self.state = State.CONFIRMING
                self._pending_intent = intent
                self._speech_buffer = []
                self._silence_frames = 0
            case IntentType.CLOSE:
                pass  # TODO: implement window close
            case IntentType.UNKNOWN:
                self.feedback.play_error()

    async def _execute_confirmed(self, intent: Intent | None) -> None:
        """Execute a confirmed dangerous action."""
        if intent is None:
            return
        match intent.type:
            case IntentType.SHUTDOWN:
                shutdown()
            case IntentType.REBOOT:
                reboot()

    def _auto_mute(self) -> None:
        """Reduce volume to ~10% during listening."""
        try:
            self._saved_volume = volume_get()
            volume_set(int(self._saved_volume * 100 * 0.1))
        except Exception:
            pass

    def _auto_unmute(self) -> None:
        """Restore volume."""
        if self._saved_volume is not None:
            try:
                volume_set(int(self._saved_volume * 100))
            except Exception:
                pass
            self._saved_volume = None
