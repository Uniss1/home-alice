# Media Assistant

**Полностью локальный голосовой ассистент для управления медиа и ПК на Windows.**

Скажите "Джарвис, включи Интерстеллар" — и фильм запустится в браузере на полный экран. Без облака, без подписок, без задержек на сеть.

## Возможности

- **Голосовое управление медиа** — поиск и воспроизведение видео через YouTube
- **Управление воспроизведением** — пауза, продолжение, следующий/предыдущий трек, полный экран
- **Громкость** — "громче", "тише", "громкость 50"
- **Системные команды** — выключение и перезагрузка с голосовым подтверждением
- **Эхоподавление** — распознаёт голос даже при играющем видео на колонках
- **Автоприглушение** — при активации звук снижается до 10%, после команды восстанавливается

## Быстрый старт

### 1. Зависимости

```bash
pip install -r media_assistant/requirements.txt
ollama pull qwen3:4b
```

### 2. Браузер

Запустите Chrome с отладочным портом:

```bash
chrome.exe --remote-debugging-port=9222
```

### 3. Конфигурация

```bash
cp media_assistant/config.example.yaml media_assistant/config.yaml
```

### 4. Запуск

```bash
python -m media_assistant.main
```

## Требования

| Компонент | Минимум |
|-----------|---------|
| ОС | Windows 10/11 |
| Python | 3.12+ |
| GPU | NVIDIA с CUDA (для STT и LLM) |
| VRAM | 4 GB (STT 1.5 GB + LLM 3 GB) |
| RAM | 1 GB |
| Ollama | Установлен, `qwen3:4b` загружен |
| Chrome | Запущен с `--remote-debugging-port=9222` |

## Как это работает

```
Микрофон + WASAPI Loopback
        │
        ▼
   AEC (SpeexDSP) ── эхоподавление по reference-сигналу
        │
        ▼
   Шумоподавление (DeepFilterNet) → VAD (Silero)
        │
        ▼
   Wake Word (OpenWakeWord) ── "Джарвис"
        │                        + проверка энергии mic vs loopback
        ▼
   STT ── Whisper (произвольные фразы) / Vosk (да/нет)
        │
        ▼
   Intent Router ── Regex (<1мс, 90% команд) → LLM fallback (Qwen3-4B)
        │
        ▼
   Действие ── браузер / громкость / медиа-клавиши / система
```

### Состояния оркестратора

```
IDLE ──wake word──▶ LISTENING ──тишина──▶ PROCESSING ──▶ RESPONDING ──▶ IDLE
                                                              │
                                                    shutdown/reboot
                                                              │
                                                              ▼
                                                         CONFIRMING ──да──▶ выполнение
                                                              │
                                                            нет/таймаут
                                                              │
                                                              ▼
                                                            IDLE
```

## Голосовые команды

| Команда | Действие |
|---------|----------|
| "включи {запрос}" | Поиск и воспроизведение видео |
| "пауза" / "стоп" | Пауза воспроизведения |
| "продолжи" / "играй" | Продолжить воспроизведение |
| "громче" / "тише" | Громкость +/-10% |
| "громкость 50" | Установить громкость |
| "на весь экран" | Полноэкранный режим |
| "следующий" / "предыдущий" | Переключение треков |
| "выключи компьютер" | Выключение (с подтверждением) |
| "перезагрузи" | Перезагрузка (с подтверждением) |

Нераспознанные фразы отправляются в локальную LLM (Qwen3-4B через Ollama) для классификации.

## Технологический стек

| Модуль | Технология | CPU/GPU |
|--------|-----------|---------|
| Захват аудио | PyAudioWPatch + WASAPI | CPU |
| Эхоподавление | SpeexDSP | CPU |
| Шумоподавление | DeepFilterNet | CPU |
| VAD | Silero VAD | CPU |
| Wake word | OpenWakeWord | CPU |
| STT (точный) | faster-whisper large-v3-turbo int8 | GPU |
| STT (быстрый) | Vosk small-ru | CPU |
| Intent router | Regex + Qwen3-4B (Ollama) | CPU / GPU |
| Браузер | Playwright CDP | — |
| Громкость | pycaw | — |
| Медиа-клавиши | win32api | — |

## Структура проекта

```
media_assistant/
├── main.py              # Точка входа (asyncio)
├── config.py            # Конфигурация из YAML
├── orchestrator.py      # Стейт-машина
├── audio/
│   ├── capture.py       # Микрофон + WASAPI loopback
│   ├── aec.py           # Эхоподавление (SpeexDSP)
│   ├── noise.py         # Шумоподавление
│   └── vad.py           # Детектор речи (Silero)
├── wakeword/
│   ├── detector.py      # OpenWakeWord
│   └── verifier.py      # Защита от эхо-активации
├── stt/
│   ├── whisper_stt.py   # faster-whisper (batch)
│   ├── vosk_stt.py      # Vosk (streaming)
│   └── router.py        # Маршрутизация STT
├── intents/
│   ├── types.py         # IntentType enum + Intent
│   ├── regex_router.py  # Regex-паттерны
│   └── llm_fallback.py  # Ollama/Qwen3
├── media/
│   ├── base.py          # ABC MediaProvider
│   ├── youtube.py       # YouTube через Playwright
│   └── manager.py       # Реестр провайдеров
├── control/
│   ├── media_keys.py    # win32api медиа-клавиши
│   ├── volume.py        # pycaw
│   └── system.py        # shutdown/reboot
└── feedback/
    └── sounds.py        # Звуковые сигналы
```

## Тесты

```bash
python -m pytest tests/media_assistant/ -v
```

140 тестов: юнит-тесты всех модулей + интеграционные E2E тесты полного пайплайна. Все Windows-зависимости замоканы для запуска в WSL2/Linux.

## Конфигурация

См. [`config.example.yaml`](config.example.yaml) — пороги wake word, модели STT, URL Ollama, параметры AEC.

## Лицензия

MIT
