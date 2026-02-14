# Home Alice VPS Deployment Guide

Инструкция по развертыванию Go relay сервера на VPS.

## Вариант 1: Сборка на VPS (Рекомендуется)

### Шаг 1: Подключиться к VPS

```bash
ssh user@your-vps-ip
```

### Шаг 2: Установить Go (если не установлен)

```bash
# Скачать Go 1.22+
wget https://go.dev/dl/go1.22.0.linux-amd64.tar.gz

# Установить
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.22.0.linux-amd64.tar.gz

# Добавить в PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Проверить
go version
```

### Шаг 3: Клонировать репозиторий

```bash
git clone https://github.com/Uniss1/home-alice.git
cd home-alice/relay
```

### Шаг 4: Собрать binary

```bash
go build -o relay .
ls -lh relay  # Должен быть ~7-8MB
```

### Шаг 5: Настроить переменные окружения

```bash
# Создать .env файл
cat > .env <<'EOF'
LISTEN_ADDR=:8443
API_KEY=your-secret-key-here
TLS_CERT=/path/to/cert.pem
TLS_KEY=/path/to/key.pem
EOF

# Сгенерировать случайный API ключ
openssl rand -hex 32
# Скопировать вывод и заменить в .env
```

### Шаг 6: Получить SSL сертификат (Let's Encrypt)

```bash
# Установить certbot
sudo apt update
sudo apt install certbot

# Получить сертификат
sudo certbot certonly --standalone -d your-domain.com

# Сертификаты будут в:
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

### Шаг 7: Создать systemd service

```bash
sudo nano /etc/systemd/system/home-alice-relay.service
```

Содержимое файла:

```ini
[Unit]
Description=Home Alice Relay Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/home-alice/relay
Environment="LISTEN_ADDR=:8443"
Environment="API_KEY=your-secret-key-here"
Environment="TLS_CERT=/etc/letsencrypt/live/your-domain.com/fullchain.pem"
Environment="TLS_KEY=/etc/letsencrypt/live/your-domain.com/privkey.pem"
ExecStart=/home/your-username/home-alice/relay/relay
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Шаг 8: Запустить сервис

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable home-alice-relay

# Запустить
sudo systemctl start home-alice-relay

# Проверить статус
sudo systemctl status home-alice-relay

# Смотреть логи
sudo journalctl -u home-alice-relay -f
```

### Шаг 9: Открыть порт в firewall

```bash
# Для ufw
sudo ufw allow 8443/tcp

# Для firewalld
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --reload
```

### Шаг 10: Проверить работу

```bash
# Health check
curl https://your-domain.com:8443/health

# Должен вернуть:
# {"status":"ok","agent_connected":false}
```

---

## Вариант 2: Кросс-компиляция локально

### Шаг 1: Собрать binary локально

```bash
cd relay
GOOS=linux GOARCH=amd64 go build -o relay-linux-amd64 .
```

### Шаг 2: Загрузить на VPS

```bash
scp relay-linux-amd64 user@your-vps:/opt/home-alice/relay
```

### Шаг 3: Продолжить с шагов 5-10 из Варианта 1

---

## Быстрый старт (на VPS)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Uniss1/home-alice.git
cd home-alice/relay

# 2. Собрать
go build -o relay .

# 3. Запустить в тестовом режиме (без SSL)
LISTEN_ADDR=:8080 API_KEY=test ./relay

# 4. Проверить
curl http://localhost:8080/health
```

---

## Настройка Yandex Dialogs

1. Перейти на https://dialogs.yandex.ru/developer/
2. Создать новый навык (тип: Webhook)
3. Webhook URL: `https://your-domain.com:8443/alice/webhook`
4. Сохранить и протестировать

---

## Мониторинг

```bash
# Проверить статус
sudo systemctl status home-alice-relay

# Логи в реальном времени
sudo journalctl -u home-alice-relay -f

# Health check
curl https://your-domain.com:8443/health
```

---

## Готово!

После развертывания:
- ✅ Relay работает на VPS с HTTPS
- ✅ Systemd обеспечивает автозапуск
- ✅ Yandex Dialogs подключен
- ✅ Готов к подключению PC Agent
