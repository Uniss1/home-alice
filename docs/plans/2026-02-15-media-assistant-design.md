# Media Assistant Design

> **Дата:** 2026-02-15
> **Статус:** Одобрен
> **Архитектурный док:** [media-assistant-architecture.md](../media-assistant-architecture.md)

## Решения

- **Структура:** Монорепо — новый модуль `media_assistant/` в home_alice
- **Скоуп:** Полная реализация по архитектурному доку
- **Медиа-сайты:** Плагинная система (ABC MediaProvider), YouTube первым
- **Разбиение:** По этапам снизу вверх, ~14 git issues с зависимостями
- **Общий код:** Вынести browser, volume, system в `shared/`

## Структура проекта

```
home_alice/
├── agent/                    # Существующий relay-агент (Yandex Alice)
├── relay/                    # Go relay
├── media_assistant/          # НОВЫЙ модуль
│   ├── __init__.py
│   ├── main.py              # Entry point — asyncio event loop
│   ├── config.py            # Конфигурация (YAML)
│   ├── config.example.yaml
│   ├── requirements.txt
│   ├── audio/
│   │   ├── capture.py       # PyAudioWPatch — mic + WASAPI loopback
│   │   ├── aec.py           # SpeexDSP echo cancellation
│   │   ├── noise.py         # DeepFilterNet / RNNoise
│   │   └── vad.py           # Silero VAD
│   ├── wakeword/
│   │   ├── detector.py      # OpenWakeWord wrapper
│   │   ├── verifier.py      # Энергетический фильтр + double-check
│   │   └── models/          # .onnx модели
│   ├── stt/
│   │   ├── whisper_stt.py   # faster-whisper (batch, точный)
│   │   ├── vosk_stt.py      # Vosk (streaming, быстрый)
│   │   └── router.py        # Логика переключения
│   ├── intents/
│   │   ├── regex_router.py  # Regex-based intent matching
│   │   ├── llm_fallback.py  # Qwen3 через Ollama
│   │   └── types.py         # Intent enum + dataclasses
│   ├── media/
│   │   ├── base.py          # ABC MediaProvider
│   │   ├── youtube.py       # YouTube provider
│   │   └── manager.py       # Выбор провайдера + disambiguation
│   ├── control/
│   │   ├── volume.py        # pycaw (из shared/)
│   │   ├── media_keys.py    # win32api media keys
│   │   └── system.py        # shutdown, reboot
│   ├── feedback/
│   │   └── sounds.py        # Звуковые сигналы (beep, "ищу", "включаю")
│   └── orchestrator.py      # State machine: IDLE→LISTENING→PROCESSING→RESPONDING
└── shared/                   # Общий код
    ├── browser.py            # Playwright CDP
    ├── volume.py             # pycaw
    └── system.py             # win32gui, subprocess
```

## Этапы (Git Issues)

### Issue #1: Scaffold — проектная структура media_assistant
- Создать директории, `__init__.py`, `config.py`, `config.example.yaml`, `requirements.txt`
- Вынести общий код в `shared/`
- Entry point `main.py` с заглушками
- **Блокирует:** все остальные

### Issue #2: Audio Capture — микрофон + WASAPI loopback
- `audio/capture.py` — PyAudioWPatch, два потока (mic + loopback)
- Синхронизация потоков, ring buffer
- **Зависит от:** #1

### Issue #3: AEC — Echo Cancellation через SpeexDSP
- `audio/aec.py` — SpeexDSP `EchoCanceller`
- Temporal alignment (cross-correlation)
- **Зависит от:** #2

### Issue #4: Noise Suppression + VAD
- `audio/noise.py` — DeepFilterNet или RNNoise
- `audio/vad.py` — Silero VAD
- **Зависит от:** #3

### Issue #5: Wake Word — OpenWakeWord
- `wakeword/detector.py` — OpenWakeWord с предобученной моделью
- `wakeword/verifier.py` — энергетический фильтр (mic vs loopback)
- Тренировка кастомной модели "Джарвис" (Colab)
- **Зависит от:** #4

### Issue #6: STT — faster-whisper (batch)
- `stt/whisper_stt.py` — faster-whisper `large-v3-turbo` int8
- GPU inference, русский язык
- **Зависит от:** #4

### Issue #7: STT — Vosk (streaming) + router
- `stt/vosk_stt.py` — Vosk `small-ru`, streaming partial results
- `stt/router.py` — логика переключения (контекст → Vosk или Whisper)
- **Зависит от:** #6

### Issue #8: Intent Router — regex
- `intents/regex_router.py` — паттерны из архитектурного дока
- `intents/types.py` — Intent enum, dataclasses
- **Зависит от:** #1

### Issue #9: Intent Router — LLM fallback (Ollama + Qwen3)
- `intents/llm_fallback.py` — Ollama API, tool calling
- Fallback только если regex не сматчил
- **Зависит от:** #8

### Issue #10: Media Provider — плагинная система + YouTube
- `media/base.py` — ABC `MediaProvider` (search, play, pause, etc.)
- `media/youtube.py` — YouTube через Playwright CDP
- `media/manager.py` — выбор провайдера, disambiguation (голосовой вопрос)
- **Зависит от:** #1

### Issue #11: System Control — media keys + shared/
- `shared/browser.py`, `shared/volume.py`, `shared/system.py` — из agent/tools/
- `control/media_keys.py` — win32api VK_MEDIA_*
- Обновить agent/ для использования shared/
- **Зависит от:** #1

### Issue #12: Sound Feedback
- `feedback/sounds.py` — beep при wake word, "ищу", "включаю"
- sounddevice или winsound
- **Зависит от:** #1

### Issue #13: Orchestrator — state machine
- `orchestrator.py` — IDLE → LISTENING → PROCESSING → RESPONDING
- Связывает все компоненты: wake word → STT → intent → action
- Auto-mute при активации
- Прогрессивная обратная связь
- **Зависит от:** #5, #7, #9, #10, #11, #12

### Issue #14: Integration Tests + E2E
- Интеграционные тесты всего пайплайна
- Тесты с мок-аудио
- **Зависит от:** #13

## Граф зависимостей

```
#1 (scaffold) → #2 (audio) → #3 (AEC) → #4 (noise+VAD) → #5 (wake word)
                                                          → #6 (whisper) → #7 (vosk+router)
#1 → #8 (regex intents) → #9 (LLM fallback)
#1 → #10 (media plugins)
#1 → #11 (system control)
#1 → #12 (sound feedback)
#5 + #7 + #9 + #10 + #11 + #12 → #13 (orchestrator) → #14 (tests)
```

### Параллельные потоки работы

После scaffold (#1) можно параллельно работать над:
- **Поток A:** Audio pipeline (#2 → #3 → #4 → #5, #6 → #7)
- **Поток B:** Intents (#8 → #9)
- **Поток C:** Media plugins (#10)
- **Поток D:** System control (#11) + Sound feedback (#12)
