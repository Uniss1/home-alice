# Home Alice — Полное управление ПК через Яндекс Алису

**Дата:** 2026-02-13
**Версия:** 2 (пересмотренная архитектура)

## Цель

Полное голосовое управление домашним Windows-ПК через Яндекс Алису: переключение окон, запуск приложений, открытие видео, управление звуком, файлами, выключение — любые действия. LLM-агент на ПК сам решает, как выполнить произвольную голосовую команду.

## Архитектура

```
┌─────────┐  webhook  ┌────────────┐  WebSocket  ┌──────────────────────┐
│  Алиса   │ ────────→ │  Go-relay  │ ──────────→ │     PC Agent         │
│(Диалоги) │ ←──────── │  (VPS)     │ ←────────── │     (Python)         │
└─────────┘            └────────────┘             │                      │
                        ~100 строк Go              │  голосовой текст     │
                        ~5MB бинарник              │       ↓              │
                                                   │  ┌────────────────┐  │
                                                   │  │ GLM-4 API      │  │
                                                   │  │ (function call) │  │
                                                   │  └───────┬────────┘  │
                                                   │          ↓           │
                                                   │  ┌────────────────┐  │
                                                   │  │ PC Tools       │  │
                                                   │  │ - windows      │  │
                                                   │  │ - processes    │  │
                                                   │  │ - browser      │  │
                                                   │  │ - audio        │  │
                                                   │  │ - keyboard     │  │
                                                   │  │ - files        │  │
                                                   │  │ - system       │  │
                                                   │  └────────────────┘  │
                                                   └──────────────────────┘
```

### Компоненты

1. **Go-relay (VPS)** — минимальный прокси-сервер (~100 строк Go). Принимает webhook от Алисы, передаёт текст на ПК через WebSocket, возвращает ответ. Никакой логики.
2. **PC Agent (Windows, Python)** — «мозг» системы. Получает текст команды, отправляет в GLM-4 с описанием инструментов (function calling), выполняет действия, возвращает результат.
3. **GLM-4 API (Zhipu AI)** — бесплатный LLM с поддержкой function calling. OpenAI-совместимый API. Вызывается с ПК.

## Поток команды

1. Пользователь: "Алиса, [навык], переключи на Chrome"
2. Яндекс.Диалоги → POST webhook на Go-relay с текстом "переключи на хром"
3. Go-relay пересылает текст на ПК через WebSocket
4. PC Agent отправляет текст в GLM-4 API с описанием доступных инструментов
5. GLM-4 возвращает: tool_call `switch_window(title="Chrome")`
6. PC Agent выполняет: находит окно Chrome, переключает на него
7. PC Agent возвращает результат: "Переключил на Chrome"
8. Go-relay отвечает Алисе: "Переключил на Chrome"

## Go-relay (VPS)

### Технологии
- Go, стандартная библиотека (`net/http`, `gorilla/websocket`)

### Поведение
- `POST /alice/webhook` — принимает JSON от Яндекс.Диалогов, извлекает `request.command`, отправляет на ПК через WebSocket, ждёт ответ (таймаут 4 сек), отвечает Алисе
- `GET /ws` — WebSocket-эндпоинт для PC-агента (аутентификация через query-параметр `key`)
- `GET /health` — проверка статуса
- Если `original_utterance == "ping"` — отвечает "pong" (health check Алисы)
- Если ПК не подключён — отвечает "Компьютер сейчас недоступен"

### Конфигурация
Через переменные окружения:
```
API_KEY=секретный-ключ-для-агента
LISTEN_ADDR=:8443
TLS_CERT=cert.pem
TLS_KEY=key.pem
```

## PC Agent (Windows)

### Технологии
- Python 3.11+, `websockets`, `openai` (совместимый клиент для GLM-4), `pywin32`, `psutil`, `pycaw`, `pyautogui`

### Поведение
- Подключается к Go-relay по WebSocket, держит соединение
- Получает текст голосовой команды
- Отправляет в GLM-4 API с описанием инструментов (tools)
- Выполняет tool_call от LLM
- Может выполнять несколько tool_call подряд (цепочка действий)
- Возвращает текстовый результат для озвучивания Алисой
- При обрыве соединения — переподключение каждые 5 секунд

### Инструменты (Tools)

| Инструмент | Описание | Реализация |
|------------|----------|------------|
| `shutdown` | Выключить ПК | `subprocess.run(["shutdown", "/s", "/t", "0"])` |
| `reboot` | Перезагрузить ПК | `subprocess.run(["shutdown", "/r", "/t", "0"])` |
| `sleep_pc` | Спящий режим | `subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])` |
| `list_windows` | Список открытых окон | `win32gui.EnumWindows` |
| `switch_window` | Переключить на окно по заголовку | `win32gui.SetForegroundWindow` |
| `close_window` | Закрыть окно | `win32gui.PostMessage(hwnd, WM_CLOSE)` |
| `open_url` | Открыть URL в браузере | `webbrowser.open(url)` |
| `search_vk_video` | Поиск видео на VK | HTTP запрос к VK API `video.search` |
| `volume_set` | Установить громкость (0-100) | `pycaw` |
| `volume_mute` | Вкл/выкл звук | `pycaw` |
| `press_keys` | Нажать горячие клавиши | `pyautogui.hotkey` |
| `type_text` | Напечатать текст | `pyautogui.typewrite` |
| `run_command` | Выполнить системную команду | `subprocess.run` (с белым списком) |
| `list_processes` | Список процессов | `psutil.process_iter` |
| `kill_process` | Завершить процесс | `psutil.Process.kill` |
| `get_system_info` | Инфо о системе (CPU, RAM, диск) | `psutil` |
| `screenshot` | Сделать скриншот | `pyautogui.screenshot` |

### Безопасность
- `run_command` — белый список разрешённых команд (настраивается в config)
- API-ключ для подключения к Go-relay
- Логирование всех выполненных действий
- GLM-4 не может вызвать произвольный код — только зарегистрированные инструменты

### Конфигурация (`config.yaml`)
```yaml
server_url: "wss://your-vps.com/ws"
api_key: "секретный-ключ"

llm:
  provider: "glm4"  # или "deepseek", "kimi"
  api_key: "ваш-ключ-GLM-4"
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model: "glm-4"

vk_token: "токен-VK-API"  # для поиска видео

allowed_commands:  # белый список для run_command
  - "ipconfig"
  - "systeminfo"
  - "tasklist"
```

### GLM-4 интеграция

Используем OpenAI-совместимый API через библиотеку `openai`:

```python
from openai import OpenAI

client = OpenAI(
    api_key="ваш-ключ",
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

response = client.chat.completions.create(
    model="glm-4",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "переключи на хром"},
    ],
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",
)
```

## Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| ПК не подключён | Go-relay отвечает Алисе: "Компьютер сейчас недоступен" |
| Таймаут ответа от ПК (>4 сек) | Go-relay: "Команда принята, но ответ не получен" |
| GLM-4 API недоступен | PC Agent возвращает: "Не удалось обработать команду" |
| Инструмент вернул ошибку | PC Agent возвращает описание ошибки |
| WebSocket разорвался | PC Agent автоматически переподключается каждые 5 сек |

## Структура проекта

```
home_alice/
├── relay/                      # Go-relay (VPS)
│   ├── main.go                 # Весь сервер в одном файле
│   ├── go.mod
│   └── go.sum
├── agent/                      # PC Agent (Windows)
│   ├── main.py                 # Точка входа, WebSocket клиент
│   ├── llm_client.py           # Обёртка над GLM-4 API
│   ├── tool_executor.py        # Диспетчер инструментов
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── system.py           # shutdown, reboot, sleep, system_info
│   │   ├── windows.py          # list_windows, switch_window, close_window
│   │   ├── browser.py          # open_url, search_vk_video
│   │   ├── audio.py            # volume_set, volume_mute
│   │   ├── keyboard.py         # press_keys, type_text
│   │   └── process.py          # list_processes, kill_process
│   ├── config.yaml
│   └── requirements.txt
└── docs/
    └── plans/
```

## Будущее развитие

- Windows GUI (system tray) для агента
- Больше инструментов (управление медиаплеером, скриншоты с OCR, clipboard)
- Multi-user: регистрация, OAuth, личные кабинеты
- Мобильное приложение
- Поддержка других LLM-провайдеров (DeepSeek, Kimi, Claude) — переключение в config
