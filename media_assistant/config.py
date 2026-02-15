# media_assistant/config.py
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


def _build_nested(cls, data: dict):
    """Build a dataclass from a dict, handling nested dataclasses."""
    if data is None:
        return cls()
    fieldtypes = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key in fieldtypes and isinstance(value, dict):
            nested_cls = cls.__dataclass_fields__[key].default_factory
            kwargs[key] = _build_nested(nested_cls, value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str) -> MediaAssistantConfig:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return _build_nested(MediaAssistantConfig, data)
