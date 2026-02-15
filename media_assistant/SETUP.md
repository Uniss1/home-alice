# Инструкция по развёртыванию Media Assistant

Пошаговое руководство: от чистой Windows до работающего голосового ассистента.

---

## 1. Системные требования

| Компонент | Требование |
|-----------|-----------|
| ОС | Windows 10/11 |
| Python | 3.12+ |
| GPU | NVIDIA с поддержкой CUDA |
| VRAM | 4+ ГБ |
| RAM | 2+ ГБ свободной |
| Микрофон | Любой (USB/встроенный) |
| Колонки | Любые (для WASAPI loopback) |

---

## 2. Установка Python

Скачать с https://www.python.org/downloads/ (Windows installer, 64-bit).

При установке обязательно отметить **"Add Python to PATH"**.

Проверка:

```powershell
python --version
# Python 3.12.x
```

---

## 3. NVIDIA CUDA

### 3.1. Драйверы

Скачать последнюю версию: https://www.nvidia.com/drivers

### 3.2. CUDA Toolkit

Скачать CUDA 12.x: https://developer.nvidia.com/cuda-downloads

Проверка:

```powershell
nvidia-smi
# Должна показать GPU и версию CUDA
```

---

## 4. Ollama (локальная LLM)

### 4.1. Установка

Скачать installer: https://ollama.com/download/windows

### 4.2. Загрузка модели

```powershell
ollama pull qwen3:4b
```

### 4.3. Проверка

```powershell
ollama run qwen3:4b "Привет, скажи одно слово"
# Должна ответить на русском
```

Ollama запускается автоматически при старте Windows (tray icon). API доступно на `http://localhost:11434`.

---

## 5. Модель Vosk (STT для коротких команд)

```powershell
mkdir models
cd models
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
tar -xf vosk-model-small-ru-0.22.zip
cd ..
```

Результат: папка `models/vosk-model-small-ru-0.22/` (~45 МБ).

---

## 6. Chrome с отладочным портом

Media Assistant управляет браузером через Chrome DevTools Protocol. Нужен Chrome с открытым портом.

### 6.1. Создание ярлыка

Создайте ярлык Chrome со следующей командой:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### 6.2. Проверка

Откройте Chrome через этот ярлык, затем в другом браузере перейдите на:

```
http://localhost:9222/json
```

Должен вернуться JSON со списком вкладок.

> **Важно:** uBlock Origin и другие расширения работают — CDP подключается к реальному профилю Chrome.

---

## 7. Зависимости Python

### 7.1. Виртуальное окружение (рекомендуется)

```powershell
cd home_alice
python -m venv .venv
.venv\Scripts\activate
```

### 7.2. Установка пакетов

```powershell
pip install -r media_assistant/requirements.txt
```

### 7.3. Playwright (браузерная автоматизация)

```powershell
playwright install chromium
```

### 7.4. Проверка ключевых зависимостей

```powershell
python -c "from faster_whisper import WhisperModel; print('faster-whisper OK')"
python -c "from vosk import Model; print('vosk OK')"
python -c "import pyaudiowpatch; print('PyAudioWPatch OK')"
python -c "from pycaw.pycaw import AudioUtilities; print('pycaw OK')"
```

---

## 8. Модель Whisper (STT для произвольных фраз)

Модель скачивается автоматически при первом запуске. Для предзагрузки:

```powershell
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cuda', compute_type='int8')"
```

Займёт ~1.5 ГБ VRAM. Файлы кешируются в `~/.cache/huggingface/`.

---

## 9. Wake Word модель

### Вариант А: Использовать готовую модель (для теста)

OpenWakeWord включает предобученные английские модели. Для быстрого теста можно использовать "hey jarvis":

```powershell
python -c "import openwakeword; openwakeword.utils.download_models()"
```

### Вариант Б: Натренировать "Джарвис" (для продакшена)

1. Перейти на https://openwakeword.com или использовать Colab notebook
2. Сгенерировать синтетические сэмплы через edge-tts (русские голоса)
3. Записать 10-20 реальных произнесений "Джарвис" своим голосом
4. Добавить шумовую аугментацию (звук фильма, бытовой шум)
5. Тренировка ~30-60 минут
6. Скачать `.onnx` файл в `media_assistant/wakeword/models/jarvis.onnx`

---

## 10. Конфигурация

```powershell
copy media_assistant\config.example.yaml media_assistant\config.yaml
```

Отредактируйте `config.yaml` под свою систему:

```yaml
audio:
  sample_rate: 16000
  frame_size: 512
  mic_device: null          # null = микрофон по умолчанию

aec:
  enabled: true
  filter_length: 1024
  auto_mute_factor: 0.1     # приглушить до 10% при активации

wake_word:
  model_path: media_assistant/wakeword/models/jarvis.onnx
  threshold: 0.8            # порог уверенности (0.7-0.9)
  energy_ratio_threshold: 1.5

stt:
  whisper_model: large-v3-turbo
  whisper_device: cuda
  whisper_compute_type: int8
  vosk_model_path: models/vosk-model-small-ru-0.22
  max_listen_seconds: 5.0

llm_fallback:
  enabled: true
  ollama_url: http://localhost:11434
  model: qwen3:4b

browser_cdp_url: http://localhost:9222
```

---

## 11. Запуск

### Перед запуском убедитесь:

- [ ] Chrome запущен с `--remote-debugging-port=9222`
- [ ] Ollama запущен (иконка в трее или `ollama serve`)
- [ ] Микрофон подключён
- [ ] Колонки/наушники подключены

### Запуск ассистента:

```powershell
python -m media_assistant.main
```

---

## 12. Проверка работоспособности

### Тесты (запуск из WSL2 или Windows):

```bash
python -m pytest tests/media_assistant/ -v
# 140 tests passed
```

### Ручная проверка:

1. Скажите "Джарвис" — должен прозвучать короткий бип
2. Скажите "включи интерстеллар" — должен открыться YouTube
3. Скажите "Джарвис, пауза" — видео должно встать на паузу
4. Скажите "Джарвис, громкость 30" — громкость снизится

---

## Устранение неполадок

| Проблема | Решение |
|----------|---------|
| `No module named 'pyaudiowpatch'` | `pip install PyAudioWPatch` |
| `CUDA out of memory` | Уменьшить модель: `whisper_model: medium` в config.yaml |
| Chrome не подключается | Проверить `http://localhost:9222/json` в браузере |
| Ollama не отвечает | `ollama serve` в отдельном терминале |
| Микрофон не найден | Проверить `mic_device` в config.yaml, или установить как default в Windows |
| Wake word не срабатывает | Снизить `threshold` до 0.6-0.7 |
| Ложные срабатывания wake word | Повысить `threshold` до 0.85-0.9 |
| Эхо от колонок активирует wake word | Повысить `energy_ratio_threshold` до 2.0-3.0 |

---

## Использование ресурсов

```
В покое (ожидание wake word):
  CPU: ~3-5%  (OpenWakeWord + VAD + AEC)
  VRAM: ~0 ГБ
  RAM: ~200 МБ

При обработке команды (2-3 секунды):
  CPU: ~15-20%
  VRAM: ~1.5 ГБ (faster-whisper)
  RAM: ~500 МБ

При LLM fallback (редко):
  VRAM: +3 ГБ (Qwen3-4B)
```
