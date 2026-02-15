# ПК как устройство Яндекс Умного Дома

## Проблема

Управление ПК через навык Алисы требует 3 шага: активация навыка, ожидание загрузки, приветствие. Для простых команд (пауза, громкость) это неприемлемо долго.

## Решение

Зарегистрировать ПК как медиаустройство (тип `devices.types.media_device.tv`) в Яндекс Умном Доме. Команды работают без активации навыка — одна фраза, одно действие.

## Маппинг команд

| Голосовая команда | Smart Home Capability | Действие на ПК |
|---|---|---|
| "Поставь на паузу" | `toggle` instance `pause` | `browser_pause_video` |
| "Продолжи" / "Играй" | `toggle` instance `pause` | `browser_play_video` |
| "Громче" / "Тише" / "Громкость 50" | `range` instance `volume` | `volume_set` |
| "Выключи звук" | `toggle` instance `mute` | `volume_mute` |
| "Выключи компьютер" | `on_off` | `shutdown` / `sleep_pc` |

## Архитектура

```
Алиса (колонка) → Яндекс Cloud → Smart Home API → Go Relay (VPS) → WebSocket → Python Agent (ПК) → действие
```

Relay расширяется новыми HTTP-эндпоинтами для Smart Home API. Agent остаётся без изменений — relay транслирует Smart Home команды в существующий формат WebSocket-сообщений.

## Smart Home API эндпоинты (Go Relay)

### OAuth2 (упрощённый)

- `GET /auth` — страница авторизации (single-user, фиксированный токен)
- `POST /token` — выдача access_token

Упрощённая реализация: один пользователь, фиксированный токен в конфиге. Яндекс требует OAuth2 flow, но для личного использования достаточно минимальной реализации.

### Smart Home Provider API

- `HEAD /v1.0` — проверка доступности (отвечает 200)
- `GET /v1.0/user/unlink` — отвязка аккаунта
- `GET /v1.0/user/devices` — discovery: возвращает устройство "Мой ПК" с capabilities
- `POST /v1.0/user/devices/query` — текущее состояние устройства
- `POST /v1.0/user/devices/action` — выполнение команды

### Discovery response

```json
{
  "request_id": "...",
  "payload": {
    "user_id": "1",
    "devices": [{
      "id": "pc-1",
      "name": "Компьютер",
      "type": "devices.types.media_device.tv",
      "capabilities": [
        {"type": "devices.capabilities.on_off", "retrievable": true},
        {"type": "devices.capabilities.toggle", "retrievable": true,
         "parameters": {"instance": "pause"}},
        {"type": "devices.capabilities.toggle", "retrievable": true,
         "parameters": {"instance": "mute"}},
        {"type": "devices.capabilities.range", "retrievable": true,
         "parameters": {"instance": "volume", "unit": "unit.percent",
                        "range": {"min": 0, "max": 100, "precision": 5}}}
      ]
    }]
  }
}
```

### Action → WebSocket трансляция

Relay получает Smart Home action, транслирует в WebSocket-сообщение агенту:

```
Smart Home: {"type": "devices.capabilities.toggle", "state": {"instance": "pause", "value": true}}
  ↓
WebSocket: {"id": "...", "text": "browser_pause_video", "source": "smart_home", "tool": "browser_pause_video", "args": {}}
```

Agent выполняет инструмент напрямую (без LLM), возвращает результат.

## Регистрация в Яндекс

1. Yandex Developer Console → Умный дом → Создать провайдер
2. Указать OAuth2 и API URL-ы на relay
3. В приложении Яндекс → Устройства → Добавить устройство → выбрать провайдер
4. Пройти OAuth2 авторизацию → устройство "Компьютер" появляется в списке

## Инфраструктура

- VPS остаётся (Go Relay уже развёрнут)
- Колонка и ПК в одной сети (не влияет на архитектуру — трафик через облако)
- Новые эндпоинты добавляются в существующий Go-сервер

## Что НЕ меняется

- Python Agent — без изменений
- WebSocket протокол — расширяется полем `source` и опциональными `tool`/`args`
- Существующий навык Алисы — продолжает работать параллельно
