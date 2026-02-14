# Home Alice VPS Deployment Design (with Nginx Proxy Manager)

**Дата:** 2026-02-14
**Версия:** 1.0
**Контекст:** Развертывание Go relay сервера на VPS с использованием Nginx Proxy Manager

## Цель

Развернуть Home Alice Go relay сервер на VPS за Nginx Proxy Manager для обработки webhook от Yandex Alice и WebSocket соединений от Windows PC агента.

## Выбранный подход

**Relay за NPM** - relay работает на `localhost:8080` без TLS, Nginx Proxy Manager управляет SSL и проксирует трафик.

### Обоснование

- У пользователя уже установлен Nginx Proxy Manager
- NPM автоматически управляет Let's Encrypt сертификатами
- Упрощает конфигурацию relay (не нужен TLS)
- Централизованное управление SSL через веб-интерфейс
- Стандартный подход для микросервисов за reverse proxy

## Архитектура развертывания

```
┌─────────────────┐
│  Yandex Alice   │
│   (webhook)     │
└────────┬────────┘
         │ HTTPS POST /alice/webhook
         ↓
┌─────────────────────────────┐
│   Nginx Proxy Manager       │
│   domain.com:443            │
│   - SSL termination         │
│   - Let's Encrypt auto      │
└────────┬────────────────────┘
         │ HTTP (localhost)
         ↓
┌─────────────────────────────┐
│   Home Alice Relay          │
│   localhost:8080            │
│   - WebSocket broker        │
│   - No TLS (за NPM)         │
└────────┬────────────────────┘
         │ WebSocket
         ↓
┌─────────────────────────────┐
│   Windows PC Agent          │
│   (подключится позже)       │
└─────────────────────────────┘
```

### Ключевые моменты

- NPM обрабатывает весь внешний HTTPS трафик
- Relay работает только на localhost (без внешнего доступа)
- WebSocket соединения проходят через NPM (WSS → WS)
- Relay не нужны TLS сертификаты

## Конфигурация компонентов

### Relay Server

**Местоположение:** `/home/<user>/home-alice/relay/`

**Переменные окружения:**
```bash
LISTEN_ADDR=127.0.0.1:8080  # Только localhost, без TLS
API_KEY=<случайный 32-байтный hex ключ>
# TLS_CERT и TLS_KEY не нужны - NPM управляет SSL
```

**Systemd service:** `/etc/systemd/system/home-alice-relay.service`

```ini
[Unit]
Description=Home Alice Relay Server
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/home/<your-user>/home-alice/relay
Environment="LISTEN_ADDR=127.0.0.1:8080"
Environment="API_KEY=<your-api-key>"
ExecStart=/home/<your-user>/home-alice/relay/relay
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Функции:**
- Автозапуск при старте системы
- Автоматический перезапуск при сбое
- Логирование через journalctl

### Nginx Proxy Manager

**Proxy Host настройки:**

| Параметр | Значение |
|----------|----------|
| Domain Names | `your-domain.com` |
| Scheme | `http` |
| Forward Hostname/IP | `127.0.0.1` |
| Forward Port | `8080` |
| Cache Assets | Off |
| Block Common Exploits | On |
| WebSocket Support | **On** ✅ |
| Access List | None (или по желанию) |

**SSL настройки:**
- SSL Certificate: Request a new SSL Certificate
- Force SSL: On
- HTTP/2 Support: On
- HSTS Enabled: On (рекомендуется)
- Use a DNS Challenge: Off (используем HTTP challenge)

**Custom Nginx Configuration:**

```nginx
# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Timeouts для WebSocket
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

## Последовательность развертывания

### Этап 1: Подготовка на VPS

1. Создать директорию для проекта:
   ```bash
   mkdir -p ~/home-alice/relay
   cd ~/home-alice/relay
   ```

2. Загрузить готовый бинарник на VPS:
   ```bash
   # С локальной машины:
   scp /home/dmin/projects/home_alice/relay/relay-linux-amd64 user@vps:~/home-alice/relay/relay
   ```

3. Сделать бинарник исполняемым:
   ```bash
   chmod +x ~/home-alice/relay/relay
   ```

4. Сгенерировать API ключ:
   ```bash
   openssl rand -hex 32
   # Сохранить вывод - это ваш API_KEY
   ```

### Этап 2: Настройка systemd service

1. Создать service файл:
   ```bash
   sudo nano /etc/systemd/system/home-alice-relay.service
   ```

2. Вставить конфигурацию (заменить `<your-user>` и `<your-api-key>`)

3. Перезагрузить systemd daemon:
   ```bash
   sudo systemctl daemon-reload
   ```

4. Включить автозапуск:
   ```bash
   sudo systemctl enable home-alice-relay
   ```

5. Запустить сервис:
   ```bash
   sudo systemctl start home-alice-relay
   ```

6. Проверить статус:
   ```bash
   sudo systemctl status home-alice-relay
   ```

### Этап 3: Настройка Nginx Proxy Manager

1. Войти в веб-интерфейс NPM (обычно `http://vps-ip:81`)

2. Hosts → Proxy Hosts → Add Proxy Host

3. **Details tab:**
   - Domain Names: `your-domain.com`
   - Scheme: `http`
   - Forward Hostname/IP: `127.0.0.1`
   - Forward Port: `8080`
   - ✅ WebSocket Support

4. **SSL tab:**
   - SSL Certificate: Request a new SSL Certificate
   - ✅ Force SSL
   - Email: your-email@example.com
   - ✅ I Agree to the Let's Encrypt Terms of Service

5. **Advanced tab:**
   - Custom Nginx Configuration: вставить WebSocket конфиг

6. Save

### Этап 4: Проверка работоспособности

1. **Локальная проверка:**
   ```bash
   curl http://localhost:8080/health
   # Ожидаем: {"status":"ok","agent_connected":false}
   ```

2. **Внешняя проверка:**
   ```bash
   curl https://your-domain.com/health
   # Ожидаем: {"status":"ok","agent_connected":false}
   ```

3. **Проверка логов:**
   ```bash
   sudo journalctl -u home-alice-relay -f
   ```

4. **Проверка автозапуска:**
   ```bash
   sudo systemctl is-enabled home-alice-relay
   # Должен вернуть: enabled
   ```

## Проверка и мониторинг

### Health Checks

**Локальная проверка (на VPS):**
```bash
curl http://localhost:8080/health
```

**Внешняя проверка (через NPM):**
```bash
curl https://your-domain.com/health
```

**Ожидаемый ответ:**
```json
{
  "status": "ok",
  "agent_connected": false
}
```

После подключения Windows агента: `"agent_connected": true`

### Логирование

**Просмотр логов relay:**
```bash
# В реальном времени
sudo journalctl -u home-alice-relay -f

# Последние 50 строк
sudo journalctl -u home-alice-relay -n 50

# С фильтром по дате
sudo journalctl -u home-alice-relay --since "1 hour ago"
```

**Типичные логи при запуске:**
```
Starting Home Alice Relay Server...
Listening on 127.0.0.1:8080
Health endpoint: /health
WebSocket endpoint: /ws
Alice webhook: /alice/webhook
```

### Мониторинг состояния

**Статус сервиса:**
```bash
sudo systemctl status home-alice-relay
```

**Автозапуск:**
```bash
sudo systemctl is-enabled home-alice-relay
# Должен вернуть: enabled
```

**Проверка процесса:**
```bash
ps aux | grep relay
```

### Troubleshooting

| Проблема | Диагностика | Решение |
|----------|-------------|---------|
| Relay не запускается | `sudo journalctl -u home-alice-relay -n 50` | Проверить переменные окружения, права на файл |
| Health check не работает локально | `curl -v http://localhost:8080/health` | Проверить LISTEN_ADDR в service файле |
| Не работает через домен | Проверить NPM logs | Проверить WebSocket Support включен |
| WebSocket не подключается | `curl -v -H "Upgrade: websocket"` | Проверить Custom Nginx Config в NPM |
| SSL ошибки | NPM SSL Certificates | Перевыпустить Let's Encrypt сертификат |

## Безопасность

### API Key
- Использовать криптографически стойкий ключ (32+ байт)
- Хранить только в переменных окружения systemd
- Не коммитить в git

### Network Security
- Relay слушает только на `127.0.0.1` (не доступен снаружи)
- NPM обрабатывает весь внешний трафик
- Force SSL в NPM (весь трафик только HTTPS)

### Рекомендации
- Настроить firewall (ufw) - разрешить только 80, 443, SSH
- Регулярно обновлять NPM и систему
- Мониторить логи на подозрительную активность
- Использовать fail2ban для защиты от brute-force

## Следующие шаги

После успешного развертывания relay:

1. **Настроить Yandex Dialogs:**
   - Webhook URL: `https://your-domain.com/alice/webhook`

2. **Настроить Windows PC Agent:**
   - `server_url`: `wss://your-domain.com/ws`
   - `api_key`: тот же ключ, что и в relay

3. **Тестирование:**
   - Запустить agent на Windows ПК
   - Проверить `agent_connected: true` в /health
   - Протестировать голосовую команду через Алису

## Критерии успеха

- ✅ Relay сервис запущен и в статусе `active (running)`
- ✅ Health endpoint доступен локально
- ✅ Health endpoint доступен через домен (HTTPS)
- ✅ NPM корректно проксирует трафик
- ✅ SSL сертификат активен (Let's Encrypt)
- ✅ Логи показывают успешный запуск без ошибок
- ✅ Сервис автоматически запускается при перезагрузке VPS
