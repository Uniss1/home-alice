# Media Assistant Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fully local voice-controlled media assistant for Windows PC — wake word detection, speech recognition, intent routing, and browser-based media playback.

**Architecture:** New `media_assistant/` module in home_alice monorepo. Shared tools (browser, volume, system) extracted to `shared/`. Asyncio event loop with state machine orchestrator. All processing on Windows (CUDA GPU for STT/LLM, CPU for audio pipeline).

**Tech Stack:** Python 3.12+, PyAudioWPatch, SpeexDSP, OpenWakeWord, faster-whisper, Vosk, Silero VAD, Ollama (Qwen3-4B), Playwright CDP, pycaw, win32api.

---

## Environment Notes

- **Development:** WSL2 (tests with mocks)
- **Runtime:** Windows (real audio, GPU, win32 APIs)
- Windows-specific imports (`pycaw`, `win32gui`, `pyaudiowpatch`) must be mocked in tests
- Each task includes unit tests runnable in WSL2

---

### Task 1: Scaffold — проектная структура

**Goal:** Create `media_assistant/` module, extract shared code to `shared/`, update `agent/` imports.

**Files:**
- Create: `shared/__init__.py`, `shared/browser.py`, `shared/volume.py`, `shared/system.py`
- Create: `media_assistant/__init__.py`, `media_assistant/main.py`, `media_assistant/config.py`, `media_assistant/config.example.yaml`, `media_assistant/requirements.txt`
- Create: all subpackage `__init__.py` files (audio/, wakeword/, stt/, intents/, media/, control/, feedback/)
- Modify: `agent/tools/audio.py` — import from `shared.volume`
- Modify: `agent/tools/browser_control.py` — import from `shared.browser`
- Modify: `agent/tools/system.py` — import from `shared.system`

**Step 1: Create shared/ with extracted code**

`shared/volume.py` — extract `_get_volume_interface()`, `volume_set()`, `volume_mute()` from `agent/tools/audio.py`:
```python
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def _get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

def volume_set(level: int) -> str:
    vol = _get_volume_interface()
    vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
    return f"Громкость: {level}%"

def volume_mute(mute: bool) -> str:
    vol = _get_volume_interface()
    vol.SetMute(1 if mute else 0, None)
    return "Звук выключен" if mute else "Звук включён"

def volume_get() -> float:
    """Return current volume level 0.0-1.0."""
    vol = _get_volume_interface()
    return vol.GetMasterVolumeLevelScalar()
```

`shared/browser.py` — extract `BrowserController` from `agent/tools/browser_control.py` (full class, unchanged).

`shared/system.py` — extract `shutdown()`, `reboot()`, `sleep_pc()`, `get_system_info()` from `agent/tools/system.py`.

**Step 2: Update agent/tools/ to re-export from shared/**

`agent/tools/audio.py`:
```python
from shared.volume import volume_set, volume_mute
```

`agent/tools/browser_control.py`:
```python
from shared.browser import BrowserController
```

`agent/tools/system.py`:
```python
from shared.system import shutdown, reboot, sleep_pc, get_system_info
```

**Step 3: Create media_assistant/ skeleton**

`media_assistant/config.py`:
```python
from dataclasses import dataclass, field
import yaml

@dataclass
class AudioConfig:
    sample_rate: int = 16000
    frame_size: int = 512
    mic_device: str | None = None  # None = default

@dataclass
class AECConfig:
    enabled: bool = True
    filter_length: int = 1024
    auto_mute_factor: float = 0.1  # reduce to 10% on wake

@dataclass
class WakeWordConfig:
    model_path: str = "media_assistant/wakeword/models/jarvis.onnx"
    threshold: float = 0.8
    energy_ratio_threshold: float = 1.5

@dataclass
class STTConfig:
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "int8"
    vosk_model_path: str = "models/vosk-model-small-ru-0.22"
    max_listen_seconds: float = 5.0

@dataclass
class LLMFallbackConfig:
    enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    model: str = "qwen3:4b"

@dataclass
class MediaAssistantConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    aec: AECConfig = field(default_factory=AECConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    llm_fallback: LLMFallbackConfig = field(default_factory=LLMFallbackConfig)
    browser_cdp_url: str = "http://localhost:9222"

def load_config(path: str) -> MediaAssistantConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    # Build config from YAML with defaults
    ...
```

`media_assistant/main.py`:
```python
import asyncio
from media_assistant.config import load_config

async def main():
    config = load_config("media_assistant/config.yaml")
    # TODO: Initialize components
    print("Media Assistant starting...")

if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run existing agent tests**

Run: `pytest tests/agent/ -v`
Expected: All 32 tests pass (imports updated, behavior unchanged)

**Step 5: Commit**

```bash
git add shared/ media_assistant/ agent/tools/
git commit -m "feat: scaffold media_assistant module and extract shared code"
```

**Acceptance Criteria:**
- [ ] `shared/` contains browser, volume, system modules
- [ ] `agent/` tests all pass with updated imports
- [ ] `media_assistant/` skeleton with config, main, all subpackage dirs
- [ ] `requirements.txt` with all new dependencies

---

### Task 2: Audio Capture — микрофон + WASAPI loopback

**Goal:** Capture microphone and system audio (loopback) simultaneously via PyAudioWPatch.

**Files:**
- Create: `media_assistant/audio/capture.py`
- Create: `tests/media_assistant/audio/test_capture.py`

**Key interfaces:**

```python
import numpy as np
from collections import deque
from dataclasses import dataclass

@dataclass
class AudioFrame:
    mic: np.ndarray       # int16, mono, 16kHz
    loopback: np.ndarray  # int16, mono, 16kHz
    timestamp: float

class AudioCapture:
    def __init__(self, sample_rate: int = 16000, frame_size: int = 512,
                 mic_device: str | None = None):
        ...

    def start(self) -> None:
        """Start mic + loopback capture threads."""

    def stop(self) -> None:
        """Stop capture, release resources."""

    def read_frame(self, timeout: float = 1.0) -> AudioFrame | None:
        """Read next synchronized frame from ring buffer."""

    @property
    def is_running(self) -> bool: ...
```

**Implementation details:**
- Two PyAudioWPatch streams: mic input + WASAPI loopback
- Ring buffer (deque, ~2s) for each stream
- Synchronization: align by timestamp, resample loopback to 16kHz mono if needed
- Thread-safe queue for consumer

**Tests (mocked PyAudioWPatch):**
```python
def test_audio_capture_starts_and_stops():
    # Mock PyAudio, verify streams opened/closed

def test_read_frame_returns_synchronized_data():
    # Feed mock data to both streams, verify AudioFrame

def test_read_frame_timeout():
    # No data → returns None after timeout

def test_loopback_resampled_to_mono_16khz():
    # Feed stereo 48kHz loopback, verify mono 16kHz output
```

**Commit:** `feat(media): add audio capture with mic and WASAPI loopback`

---

### Task 3: AEC — Echo Cancellation через SpeexDSP

**Goal:** Remove echo from microphone using loopback as reference signal.

**Files:**
- Create: `media_assistant/audio/aec.py`
- Create: `tests/media_assistant/audio/test_aec.py`

**Key interfaces:**

```python
class EchoCanceller:
    def __init__(self, frame_size: int = 160, filter_length: int = 1024,
                 sample_rate: int = 16000):
        from speexdsp import EchoCanceller as SpxEC
        self._ec = SpxEC.create(frame_size, filter_length, sample_rate)

    def process(self, mic_frame: np.ndarray, ref_frame: np.ndarray) -> np.ndarray:
        """Cancel echo: mic - reference → clean signal."""
        mic_bytes = mic_frame.tobytes()
        ref_bytes = ref_frame.tobytes()
        clean_bytes = self._ec.process(mic_bytes, ref_bytes)
        return np.frombuffer(clean_bytes, dtype=np.int16)

    def reset(self) -> None:
        """Reset adaptive filter state."""
```

**Implementation details:**
- SpeexDSP adaptive filter (NLMS-based)
- Frame size 160 samples (10ms at 16kHz) for SpeexDSP
- Audio capture frame_size (512) needs to be chunked to 160
- Temporal alignment: cross-correlation for initial delay estimate

**Tests:**
```python
def test_echo_canceller_reduces_reference():
    # mic = voice + reference, verify output has less reference

def test_echo_canceller_preserves_voice():
    # mic = pure voice (no echo), verify output ≈ input

def test_reset_clears_state():
    # Process frames, reset, verify fresh state
```

**Commit:** `feat(media): add SpeexDSP echo cancellation`

---

### Task 4: Noise Suppression + VAD

**Goal:** Clean audio with noise suppression, detect speech with Silero VAD.

**Files:**
- Create: `media_assistant/audio/noise.py`
- Create: `media_assistant/audio/vad.py`
- Create: `tests/media_assistant/audio/test_noise.py`
- Create: `tests/media_assistant/audio/test_vad.py`

**Noise suppression interface:**

```python
class NoiseSuppressor:
    def __init__(self, method: str = "deepfilter"):
        # Load DeepFilterNet or RNNoise

    def process(self, frame: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Suppress noise, return clean frame."""
```

**VAD interface:**

```python
class VoiceActivityDetector:
    def __init__(self, threshold: float = 0.5):
        import torch
        self.model, self.utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
        self.threshold = threshold

    def is_speech(self, frame: np.ndarray, sample_rate: int = 16000) -> bool:
        """Return True if frame contains speech."""

    def reset(self) -> None:
        """Reset internal state between utterances."""
```

**Tests:**
```python
def test_noise_suppressor_reduces_noise():
    # noisy signal → output has lower noise floor

def test_vad_detects_speech():
    # frame with speech → True

def test_vad_rejects_silence():
    # silent frame → False

def test_vad_rejects_noise():
    # noise-only frame → False
```

**Commit:** `feat(media): add noise suppression and Silero VAD`

---

### Task 5: Wake Word — OpenWakeWord + верификация

**Goal:** Detect "Джарвис" wake word with false-positive protection.

**Files:**
- Create: `media_assistant/wakeword/detector.py`
- Create: `media_assistant/wakeword/verifier.py`
- Create: `tests/media_assistant/wakeword/test_detector.py`
- Create: `tests/media_assistant/wakeword/test_verifier.py`

**Detector interface:**

```python
class WakeWordDetector:
    def __init__(self, model_path: str, threshold: float = 0.8):
        import openwakeword
        self.model = openwakeword.Model(wakeword_models=[model_path])
        self.threshold = threshold

    def process_frame(self, frame: np.ndarray) -> float:
        """Return confidence score for wake word in frame (0.0-1.0)."""

    def detected(self, frame: np.ndarray) -> bool:
        """Return True if wake word detected above threshold."""

    def reset(self) -> None:
        """Reset detector state."""
```

**Verifier interface:**

```python
class WakeWordVerifier:
    def __init__(self, energy_ratio_threshold: float = 1.5,
                 confidence_threshold: float = 0.8):
        self.energy_ratio_threshold = energy_ratio_threshold
        self.confidence_threshold = confidence_threshold

    def verify(self, mic_energy: float, loopback_energy: float,
               oww_confidence: float) -> bool:
        """Verify wake word is from real person, not from speakers."""
        energy_ratio = mic_energy / (loopback_energy + 1e-10)
        return (oww_confidence >= self.confidence_threshold
                and energy_ratio >= self.energy_ratio_threshold)
```

**Tests:**
```python
def test_detector_returns_confidence():
    # Mock openwakeword, verify float return

def test_detector_threshold():
    # confidence > threshold → detected=True

def test_verifier_accepts_real_voice():
    # mic_energy >> loopback_energy, high confidence → True

def test_verifier_rejects_speaker_echo():
    # mic_energy ≈ loopback_energy → False (sound from speakers)

def test_verifier_rejects_low_confidence():
    # high energy ratio but low confidence → False
```

**Note:** Custom "Джарвис" model training is a separate manual step (Colab notebook). Use pretrained English model for initial development.

**Commit:** `feat(media): add OpenWakeWord detector with energy-based verification`

---

### Task 6: STT — faster-whisper (batch)

**Goal:** High-accuracy speech-to-text for arbitrary Russian phrases.

**Files:**
- Create: `media_assistant/stt/whisper_stt.py`
- Create: `tests/media_assistant/stt/test_whisper_stt.py`

**Interface:**

```python
class WhisperSTT:
    def __init__(self, model_name: str = "large-v3-turbo",
                 device: str = "cuda", compute_type: str = "int8"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_name, device=device,
                                  compute_type=compute_type)

    def transcribe(self, audio: np.ndarray, language: str = "ru") -> str:
        """Transcribe audio array to text. Returns lowercase stripped text."""
        segments, _ = self.model.transcribe(audio, language=language)
        return " ".join(s.text for s in segments).strip().lower()
```

**Tests:**
```python
def test_transcribe_returns_text():
    # Mock WhisperModel, verify segments joined

def test_transcribe_returns_lowercase():
    # Verify output is lowercased

def test_transcribe_empty_audio():
    # Empty/silent audio → empty string
```

**Commit:** `feat(media): add faster-whisper STT`

---

### Task 7: STT — Vosk (streaming) + router

**Goal:** Fast streaming STT for short commands + routing logic.

**Files:**
- Create: `media_assistant/stt/vosk_stt.py`
- Create: `media_assistant/stt/router.py`
- Create: `tests/media_assistant/stt/test_vosk_stt.py`
- Create: `tests/media_assistant/stt/test_router.py`

**Vosk interface:**

```python
class VoskSTT:
    def __init__(self, model_path: str, sample_rate: int = 16000):
        from vosk import Model, KaldiRecognizer
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, sample_rate)

    def feed_frame(self, frame: np.ndarray) -> str | None:
        """Feed audio frame. Return partial result or None."""
        if self.recognizer.AcceptWaveform(frame.tobytes()):
            result = json.loads(self.recognizer.Result())
            return result.get("text", "")
        return None

    def get_partial(self) -> str:
        """Get current partial recognition result."""
        result = json.loads(self.recognizer.PartialResult())
        return result.get("partial", "")

    def reset(self) -> None:
        """Reset recognizer for new utterance."""
```

**Router interface:**

```python
class STTRouter:
    def __init__(self, whisper: WhisperSTT, vosk: VoskSTT):
        self.whisper = whisper
        self.vosk = vosk

    def transcribe(self, audio: np.ndarray, context: str = "general") -> str:
        """Route to Vosk (confirmation) or Whisper (general)."""
        if context == "confirmation":
            # Use Vosk streaming for yes/no
            for chunk in np.array_split(audio, max(1, len(audio) // 512)):
                result = self.vosk.feed_frame(chunk)
                if result:
                    return result
            return ""
        else:
            return self.whisper.transcribe(audio)
```

**Tests:**
```python
def test_vosk_feed_frame_returns_text():
def test_vosk_partial_result():
def test_router_uses_whisper_for_general():
def test_router_uses_vosk_for_confirmation():
```

**Commit:** `feat(media): add Vosk streaming STT and STT router`

---

### Task 8: Intent Router — regex

**Goal:** Fast regex-based intent matching for known commands.

**Files:**
- Create: `media_assistant/intents/types.py`
- Create: `media_assistant/intents/regex_router.py`
- Create: `tests/media_assistant/intents/test_types.py`
- Create: `tests/media_assistant/intents/test_regex_router.py`

**Types:**

```python
from enum import Enum
from dataclasses import dataclass

class IntentType(Enum):
    PLAY_MEDIA = "play_media"
    PAUSE = "pause"
    RESUME = "resume"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    SHUTDOWN = "shutdown"
    REBOOT = "reboot"
    FULLSCREEN = "fullscreen"
    CLOSE = "close"
    NEXT_TRACK = "next_track"
    PREV_TRACK = "prev_track"
    UNKNOWN = "unknown"

@dataclass
class Intent:
    type: IntentType
    query: str = ""       # e.g. "интерстеллар" for PLAY_MEDIA
    params: dict = field(default_factory=dict)  # e.g. {"level": 50} for VOLUME_SET
```

**Regex router:**

```python
import re

PATTERNS: list[tuple[str, IntentType, str | None]] = [
    (r"(?:включи|поставь|запусти)\s+(.+)", IntentType.PLAY_MEDIA, "query"),
    (r"(?:пауза|стоп|останови)", IntentType.PAUSE, None),
    (r"(?:продолжи|играй|play)", IntentType.RESUME, None),
    (r"(?:громче|прибавь звук)", IntentType.VOLUME_UP, None),
    (r"(?:тише|убавь звук)", IntentType.VOLUME_DOWN, None),
    (r"(?:громкость)\s+(\d+)", IntentType.VOLUME_SET, "level"),
    (r"(?:выключи компьютер|shutdown)", IntentType.SHUTDOWN, None),
    (r"(?:перезагрузи|перезагрузка)", IntentType.REBOOT, None),
    (r"(?:на весь экран|фулскрин|fullscreen)", IntentType.FULLSCREEN, None),
    (r"(?:закрой|выйди)", IntentType.CLOSE, None),
    (r"(?:следующ|дальше|next)", IntentType.NEXT_TRACK, None),
    (r"(?:предыдущ|назад|prev)", IntentType.PREV_TRACK, None),
]

class RegexIntentRouter:
    def route(self, text: str) -> Intent:
        text = text.lower().strip()
        for pattern, intent_type, capture_name in PATTERNS:
            m = re.match(pattern, text)
            if m:
                if capture_name == "query" and m.lastindex:
                    return Intent(type=intent_type, query=m.group(1))
                elif capture_name == "level" and m.lastindex:
                    return Intent(type=intent_type, params={"level": int(m.group(1))})
                return Intent(type=intent_type)
        return Intent(type=IntentType.UNKNOWN, query=text)
```

**Tests:**
```python
def test_play_media_intent():
    router = RegexIntentRouter()
    intent = router.route("включи интерстеллар")
    assert intent.type == IntentType.PLAY_MEDIA
    assert intent.query == "интерстеллар"

def test_pause_intent():
    assert router.route("пауза").type == IntentType.PAUSE

def test_volume_set_intent():
    intent = router.route("громкость 50")
    assert intent.type == IntentType.VOLUME_SET
    assert intent.params["level"] == 50

def test_unknown_intent():
    assert router.route("какая погода").type == IntentType.UNKNOWN

# Test all patterns from PATTERNS list
# Test case insensitivity
# Test whitespace handling
```

**Commit:** `feat(media): add regex intent router with Russian command patterns`

---

### Task 9: Intent Router — LLM fallback (Ollama + Qwen3)

**Goal:** Use local LLM to classify commands that don't match regex patterns.

**Files:**
- Create: `media_assistant/intents/llm_fallback.py`
- Create: `tests/media_assistant/intents/test_llm_fallback.py`

**Interface:**

```python
import httpx

class LLMFallbackRouter:
    def __init__(self, ollama_url: str = "http://localhost:11434",
                 model: str = "qwen3:4b"):
        self.ollama_url = ollama_url
        self.model = model
        self.tools = [...]  # Tool definitions matching IntentType enum

    def route(self, text: str) -> Intent:
        """Send unrecognized text to LLM, parse tool call as intent."""
        resp = httpx.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "tools": self.tools,
                "stream": False,
            },
            timeout=5.0,
        )
        # Parse tool call from response → Intent
        ...

    def is_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = httpx.get(f"{self.ollama_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except httpx.ConnectError:
            return False
```

**Tests:**
```python
def test_llm_fallback_parses_tool_call():
    # Mock httpx response with tool call → correct Intent

def test_llm_fallback_timeout():
    # Ollama slow → returns UNKNOWN intent

def test_is_available_check():
    # Mock httpx → True/False
```

**Commit:** `feat(media): add LLM fallback intent router via Ollama`

---

### Task 10: Media Provider — плагинная система + YouTube

**Goal:** Abstract media provider interface, YouTube implementation via Playwright CDP.

**Files:**
- Create: `media_assistant/media/base.py`
- Create: `media_assistant/media/youtube.py`
- Create: `media_assistant/media/manager.py`
- Create: `tests/media_assistant/media/test_youtube.py`
- Create: `tests/media_assistant/media/test_manager.py`

**Base interface:**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class MediaResult:
    title: str
    url: str
    provider: str
    thumbnail: str = ""

class MediaProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[MediaResult]:
        """Search for media by query."""

    @abstractmethod
    def play(self, result: MediaResult) -> str:
        """Navigate to media and start playback. Return status message."""

    @abstractmethod
    def pause(self) -> str:
        """Pause current playback."""

    @abstractmethod
    def resume(self) -> str:
        """Resume current playback."""

    @abstractmethod
    def fullscreen(self) -> str:
        """Toggle fullscreen."""
```

**YouTube provider:**

```python
from shared.browser import BrowserController

class YouTubeProvider(MediaProvider):
    name = "youtube"

    def __init__(self, browser: BrowserController):
        self.browser = browser

    def search(self, query: str, limit: int = 5) -> list[MediaResult]:
        # Navigate to youtube.com/results?search_query={query}
        # Parse results via page.query_selector_all
        ...

    def play(self, result: MediaResult) -> str:
        # Navigate to result.url
        # Wait for video element
        # Click play, request fullscreen
        ...
```

**Media manager:**

```python
class MediaManager:
    def __init__(self):
        self.providers: dict[str, MediaProvider] = {}
        self.active_provider: MediaProvider | None = None

    def register(self, provider: MediaProvider) -> None:
        self.providers[provider.name] = provider

    def play(self, query: str) -> str:
        """Search across providers, play best result."""
        # For now: use first registered provider
        provider = list(self.providers.values())[0]
        results = provider.search(query)
        if not results:
            return f"Не нашёл «{query}»"
        if len(results) == 1:
            self.active_provider = provider
            return provider.play(results[0])
        # Multiple results → return list for disambiguation
        return results  # Orchestrator handles voice disambiguation
```

**Tests:**
```python
def test_youtube_search_returns_results():
    # Mock Playwright page → MediaResult list

def test_youtube_play_navigates_and_starts():
    # Mock Playwright → verify navigation + play

def test_manager_registers_provider():
def test_manager_play_single_result():
def test_manager_play_no_results():
def test_manager_play_multiple_results_returns_list():
```

**Commit:** `feat(media): add plugin-based media provider system with YouTube`

---

### Task 11: System Control — media keys + shared/

**Goal:** Media keys via win32api, ensure shared/ modules work for media_assistant.

**Files:**
- Create: `media_assistant/control/media_keys.py`
- Create: `media_assistant/control/volume.py`
- Create: `media_assistant/control/system.py`
- Create: `tests/media_assistant/control/test_media_keys.py`

**Media keys:**

```python
import win32api
import win32con

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

def press_media_key(vk_code: int) -> None:
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)

def play_pause() -> str:
    press_media_key(VK_MEDIA_PLAY_PAUSE)
    return "Play/Pause"

def next_track() -> str:
    press_media_key(VK_MEDIA_NEXT_TRACK)
    return "Следующий трек"

def prev_track() -> str:
    press_media_key(VK_MEDIA_PREV_TRACK)
    return "Предыдущий трек"
```

**Volume/system control — thin wrappers:**

```python
# media_assistant/control/volume.py
from shared.volume import volume_set, volume_mute, volume_get

# media_assistant/control/system.py
from shared.system import shutdown, reboot, sleep_pc
```

**Tests:**
```python
@patch("media_assistant.control.media_keys.win32api")
def test_play_pause(mock_api):
    result = play_pause()
    assert mock_api.keybd_event.call_count == 2  # press + release

@patch("media_assistant.control.media_keys.win32api")
def test_next_track(mock_api):
    result = next_track()
    mock_api.keybd_event.assert_any_call(0xB0, 0, 0, 0)
```

**Commit:** `feat(media): add media key control via win32api`

---

### Task 12: Sound Feedback

**Goal:** Audio feedback for user interaction (beep on wake, "ищу", "включаю").

**Files:**
- Create: `media_assistant/feedback/sounds.py`
- Create: `tests/media_assistant/feedback/test_sounds.py`

**Interface:**

```python
import numpy as np

class SoundFeedback:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        # Pregenerate beep tones
        self._wake_beep = self._generate_beep(freq=880, duration=0.05)
        self._confirm_beep = self._generate_beep(freq=440, duration=0.1)
        self._error_beep = self._generate_beep(freq=220, duration=0.2)

    def _generate_beep(self, freq: float, duration: float) -> np.ndarray:
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        return (np.sin(2 * np.pi * freq * t) * 0.5 * 32767).astype(np.int16)

    def play_wake(self) -> None:
        """Short high beep — wake word detected."""
        self._play(self._wake_beep)

    def play_searching(self) -> None:
        """Confirmation beep — processing started."""
        self._play(self._confirm_beep)

    def play_error(self) -> None:
        """Low beep — error occurred."""
        self._play(self._error_beep)

    def _play(self, audio: np.ndarray) -> None:
        import sounddevice as sd
        sd.play(audio, self.sample_rate, blocking=False)
```

**Tests:**
```python
def test_generate_beep_shape():
    fb = SoundFeedback()
    assert fb._wake_beep.dtype == np.int16
    assert len(fb._wake_beep) == int(16000 * 0.05)

@patch("media_assistant.feedback.sounds.sd")
def test_play_wake_calls_sounddevice(mock_sd):
    fb = SoundFeedback()
    fb.play_wake()
    mock_sd.play.assert_called_once()
```

**Commit:** `feat(media): add sound feedback system`

---

### Task 13: Orchestrator — state machine

**Goal:** Central event loop connecting all components with state management.

**Files:**
- Create: `media_assistant/orchestrator.py`
- Create: `tests/media_assistant/test_orchestrator.py`

**Interface:**

```python
import asyncio
from enum import Enum

class State(Enum):
    IDLE = "idle"              # Listening for wake word
    LISTENING = "listening"    # Recording speech after wake word
    PROCESSING = "processing"  # STT + intent routing
    RESPONDING = "responding"  # Executing action
    CONFIRMING = "confirming"  # Waiting for yes/no (shutdown, etc.)

class Orchestrator:
    def __init__(self, config: MediaAssistantConfig):
        self.state = State.IDLE
        # Initialize all components
        self.audio = AudioCapture(...)
        self.aec = EchoCanceller(...)
        self.noise = NoiseSuppressor(...)
        self.vad = VoiceActivityDetector(...)
        self.wake_word = WakeWordDetector(...)
        self.wake_verifier = WakeWordVerifier(...)
        self.stt_router = STTRouter(...)
        self.intent_router = RegexIntentRouter()
        self.llm_fallback = LLMFallbackRouter(...)
        self.media = MediaManager()
        self.feedback = SoundFeedback()
        self._saved_volume: float | None = None

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
        mic_energy = np.sqrt(np.mean(frame.mic.astype(float) ** 2))
        loopback_energy = np.sqrt(np.mean(frame.loopback.astype(float) ** 2))

        if self.wake_verifier.verify(mic_energy, loopback_energy, confidence):
            self.feedback.play_wake()
            self._auto_mute()
            self.state = State.LISTENING
            self._speech_buffer = []
            self._silence_frames = 0

    async def _handle_listening(self, clean: np.ndarray) -> None:
        self._speech_buffer.append(clean)
        is_speech = self.vad.is_speech(clean)

        if not is_speech:
            self._silence_frames += 1
        else:
            self._silence_frames = 0

        # End of utterance: 0.5s silence or 5s max
        total_seconds = len(self._speech_buffer) * 512 / 16000
        if self._silence_frames > 8 or total_seconds > 5.0:
            self.state = State.PROCESSING
            audio = np.concatenate(self._speech_buffer)
            text = self.stt_router.transcribe(audio, context="general")
            await self._route_intent(text)

    async def _route_intent(self, text: str) -> None:
        self.feedback.play_searching()
        intent = self.intent_router.route(text)
        if intent.type == IntentType.UNKNOWN:
            if self.llm_fallback.is_available():
                intent = self.llm_fallback.route(text)

        self.state = State.RESPONDING
        await self._execute_intent(intent)
        self._auto_unmute()
        self.state = State.IDLE

    async def _execute_intent(self, intent: Intent) -> None:
        match intent.type:
            case IntentType.PLAY_MEDIA:
                result = self.media.play(intent.query)
                # If multiple results → voice disambiguation
            case IntentType.PAUSE:
                self.media.active_provider.pause()
            case IntentType.RESUME:
                self.media.active_provider.resume()
            case IntentType.VOLUME_SET:
                volume_set(intent.params["level"])
            case IntentType.SHUTDOWN:
                self.state = State.CONFIRMING
                # Wait for "да" via Vosk
            # ... etc

    def _auto_mute(self) -> None:
        """Reduce volume to 10% during listening."""
        self._saved_volume = volume_get()
        volume_set(int(self._saved_volume * 100 * 0.1))

    def _auto_unmute(self) -> None:
        """Restore volume."""
        if self._saved_volume is not None:
            volume_set(int(self._saved_volume * 100))
            self._saved_volume = None
```

**Tests:**
```python
def test_state_transitions_idle_to_listening():
    # Wake word detected → state changes to LISTENING

def test_state_transitions_listening_to_processing():
    # Silence after speech → state changes to PROCESSING

def test_auto_mute_on_wake():
    # Wake word → volume reduced to 10%

def test_auto_unmute_after_action():
    # Action complete → volume restored

def test_shutdown_requires_confirmation():
    # Shutdown intent → state = CONFIRMING

def test_unknown_intent_falls_back_to_llm():
    # Regex miss → LLM fallback called
```

**Commit:** `feat(media): add orchestrator state machine`

---

### Task 14: Integration Tests + E2E

**Goal:** End-to-end tests with mocked audio, verify full pipeline.

**Files:**
- Create: `tests/media_assistant/test_integration.py`
- Create: `tests/media_assistant/conftest.py` (shared fixtures)

**Test scenarios:**

```python
def test_e2e_wake_word_to_play_media():
    """Full pipeline: wake word → STT → intent → play video."""
    # 1. Feed audio with wake word → state changes
    # 2. Feed audio with "включи интерстеллар" → STT → intent
    # 3. Verify browser navigated to YouTube, searched, played

def test_e2e_pause_resume():
    """Wake → "пауза" → video paused. Wake → "продолжи" → video resumed."""

def test_e2e_volume_control():
    """Wake → "громкость 50" → volume set to 50%."""

def test_e2e_shutdown_confirmation():
    """Wake → "выключи компьютер" → wait → "да" → shutdown called."""

def test_e2e_shutdown_rejection():
    """Wake → "выключи компьютер" → wait → "нет" → back to IDLE."""

def test_e2e_unknown_intent_llm_fallback():
    """Wake → unrecognized phrase → LLM fallback → correct intent."""

def test_e2e_aec_filters_echo():
    """Playing audio + voice command → AEC removes echo → correct STT."""
```

**Commit:** `test(media): add integration tests for full pipeline`

---

## Dependency Graph

```
Task 1 (scaffold) ─┬─→ Task 2 (audio) → Task 3 (AEC) → Task 4 (noise+VAD) ─┬→ Task 5 (wake word)
                    │                                                          └→ Task 6 (whisper) → Task 7 (vosk)
                    ├─→ Task 8 (regex intents) → Task 9 (LLM fallback)
                    ├─→ Task 10 (media plugins)
                    ├─→ Task 11 (system control)
                    └─→ Task 12 (sound feedback)

Tasks 5 + 7 + 9 + 10 + 11 + 12 → Task 13 (orchestrator) → Task 14 (integration tests)
```

## Parallel Streams (after Task 1)

| Stream | Tasks | Can run in parallel |
|--------|-------|-------------------|
| A: Audio Pipeline | 2 → 3 → 4 → 5, 6 → 7 | Yes |
| B: Intents | 8 → 9 | Yes |
| C: Media Plugins | 10 | Yes |
| D: Controls + Feedback | 11, 12 | Yes |
| E: Integration | 13 → 14 | After A+B+C+D |
