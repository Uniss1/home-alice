# Docker Containerization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Containerize Go Relay server with multi-stage Docker build and Nginx Proxy Manager integration.

**Architecture:** Multi-stage Dockerfile (golang:1.22-alpine builder + alpine runtime) produces minimal ~10-15MB image. Container runs in existing nginx_default network, NPM handles SSL/TLS termination and proxies to relay:8080. Agent config updated to connect via NPM domain.

**Tech Stack:** Docker, Docker Compose, Alpine Linux, Nginx Proxy Manager

---

## Task 1: Create .dockerignore

**Files:**
- Create: `relay/.dockerignore`

**Step 1: Create .dockerignore file**

Create `relay/.dockerignore`:
```
# Documentation
*.md
README.md
DEPLOYMENT.md

# Compiled binaries
relay
relay-linux-amd64
relay-*

# Git
.git
.gitignore

# Environment
.env
.env.*

# Go
*.test
*.out
coverage.txt

# IDE
.vscode
.idea
*.swp
*.swo
```

**Step 2: Verify file created**

Run: `cat relay/.dockerignore`
Expected: File content displays correctly

**Step 3: Commit**

```bash
git add relay/.dockerignore
git commit -m "build: add .dockerignore for Docker build optimization"
```

---

## Task 2: Create Dockerfile with multi-stage build

**Files:**
- Create: `relay/Dockerfile`

**Step 1: Create multi-stage Dockerfile**

Create `relay/Dockerfile`:
```dockerfile
# Stage 1: Builder
FROM golang:1.22-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates

WORKDIR /build

# Copy go module files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build static binary with optimizations
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags='-w -s -extldflags "-static"' \
    -a \
    -o relay \
    .

# Stage 2: Runtime
FROM alpine:latest

# Install runtime dependencies
RUN apk add --no-cache ca-certificates wget

# Create non-root user
RUN addgroup -S relay && adduser -S relay -G relay

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/relay .

# Change ownership
RUN chown -R relay:relay /app

# Switch to non-root user
USER relay

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Run
CMD ["./relay"]
```

**Step 2: Verify Dockerfile syntax**

Run: `cd relay && docker build --no-cache -t home-alice-relay:test .`
Expected: Build completes successfully, shows two stages

**Step 3: Check image size**

Run: `docker images home-alice-relay:test`
Expected: Size approximately 10-20MB (much smaller than 800MB golang image)

**Step 4: Test image runs**

Run: `LISTEN_ADDR=:8080 API_KEY=test docker run --rm -e LISTEN_ADDR -e API_KEY -p 8080:8080 home-alice-relay:test`
Expected: Container starts, relay listens on :8080

**Step 5: Clean up test**

Run: `docker rmi home-alice-relay:test`

**Step 6: Commit**

```bash
git add relay/Dockerfile
git commit -m "build: add multi-stage Dockerfile for minimal Go relay image"
```

---

## Task 3: Create docker-compose.yml

**Files:**
- Create: `relay/docker-compose.yml`

**Step 1: Create docker-compose.yml**

Create `relay/docker-compose.yml`:
```yaml
version: '3.8'

services:
  relay:
    container_name: home-alice-relay
    build:
      context: .
      dockerfile: Dockerfile
    image: home-alice-relay:latest
    restart: unless-stopped
    environment:
      - LISTEN_ADDR=${LISTEN_ADDR:-:8080}
      - API_KEY=${API_KEY}
    networks:
      - nginx_default
    ports:
      - "8080"  # Internal only, not exposed to host
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      start_period: 5s
      retries: 3

networks:
  nginx_default:
    external: true
```

**Step 2: Validate docker-compose syntax**

Run: `cd relay && docker-compose config`
Expected: YAML parses correctly, shows resolved configuration

**Step 3: Commit**

```bash
git add relay/docker-compose.yml
git commit -m "build: add docker-compose.yml for relay deployment"
```

---

## Task 4: Create .env.example template

**Files:**
- Create: `relay/.env.example`

**Step 1: Create .env.example**

Create `relay/.env.example`:
```bash
# API Key for Agent authentication
# Generate with: openssl rand -hex 32
API_KEY=your-secret-api-key-here

# Listen address inside container
LISTEN_ADDR=:8080
```

**Step 2: Verify file created**

Run: `cat relay/.env.example`
Expected: Template displays with comments

**Step 3: Commit**

```bash
git add relay/.env.example
git commit -m "build: add .env.example template for Docker deployment"
```

---

## Task 5: Update .gitignore

**Files:**
- Modify: `relay/.gitignore` (create if doesn't exist)

**Step 1: Ensure .env is ignored**

Check if `relay/.gitignore` exists:
```bash
ls -la relay/.gitignore
```

If doesn't exist, create `relay/.gitignore`:
```
# Environment variables
.env

# Compiled binary
relay
relay-*
```

If exists, ensure `.env` is listed.

**Step 2: Verify .env won't be committed**

Run: `cd relay && touch .env && git status`
Expected: .env should NOT appear in untracked files

**Step 3: Clean up test**

Run: `rm relay/.env`

**Step 4: Commit**

```bash
git add relay/.gitignore
git commit -m "build: ensure .env is git-ignored"
```

---

## Task 6: Update DEPLOYMENT.md with Docker instructions

**Files:**
- Modify: `DEPLOYMENT.md`

**Step 1: Read current DEPLOYMENT.md**

Run: `cat DEPLOYMENT.md | head -20`
Expected: See existing deployment variants

**Step 2: Add Docker deployment section**

Add new section after existing variants in `DEPLOYMENT.md`:

```markdown
---

## Вариант 3: Docker Deployment (Рекомендуется для VPS)

### Требования

- Docker и Docker Compose установлены на VPS
- Nginx Proxy Manager настроен и работает
- Docker сеть `nginx_default` существует

### Шаг 1: Клонировать репозиторий

```bash
cd /opt
git clone https://github.com/yourusername/home-alice.git
cd home-alice/relay
```

### Шаг 2: Создать .env файл

```bash
# Сгенерировать случайный API ключ
cat > .env <<EOF
API_KEY=$(openssl rand -hex 32)
LISTEN_ADDR=:8080
EOF

# Сохранить API_KEY для настройки Agent
cat .env
```

**ВАЖНО:** Сохраните значение `API_KEY` - оно понадобится для конфигурации Agent.

### Шаг 3: Проверить Docker сеть

```bash
# Убедиться что nginx_default существует
docker network ls | grep nginx_default

# Если не существует, создать
docker network create nginx_default
```

### Шаг 4: Собрать и запустить контейнер

```bash
docker-compose up -d --build
```

**Ожидаемый вывод:**
```
Building relay
[+] Building 45.2s (15/15) FINISHED
...
Creating home-alice-relay ... done
```

### Шаг 5: Проверить статус

```bash
# Статус контейнера
docker-compose ps

# Логи
docker-compose logs -f

# Health check
docker exec home-alice-relay wget -qO- http://localhost:8080/health
```

**Ожидаемый ответ:**
```json
{"status":"ok","agent_connected":false}
```

### Шаг 6: Настроить Nginx Proxy Manager

1. Открыть NPM UI: `http://your-vps-ip:81`
2. Создать новый Proxy Host:
   - **Domain Names:** `your-domain.com`
   - **Scheme:** `http`
   - **Forward Hostname/IP:** `home-alice-relay`
   - **Forward Port:** `8080`
   - **WebSocket Support:** ✅ **Включить обязательно!**
3. **SSL Tab:**
   - Request New SSL Certificate
   - Agree to Let's Encrypt ToS
   - Force SSL: ✅
4. **Save**

### Шаг 7: Обновить конфигурацию Agent (на Windows ПК)

Отредактировать `agent/config.yaml`:

```yaml
server_url: "wss://your-domain.com/ws"  # Через NPM
api_key: "<API_KEY из .env файла VPS>"

llm:
  provider: "glm4"
  api_key: "your-glm4-api-key"
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model: "glm-4"
```

### Шаг 8: Запустить Agent

```bash
python -m agent.main
```

**Ожидаемый вывод:**
```
2026-02-14 10:30:45,123 [INFO] agent.main: Connecting to wss://your-domain.com/ws
2026-02-14 10:30:45,456 [INFO] agent.main: Connected to relay server
```

### Шаг 9: Проверить health check

```bash
curl https://your-domain.com/health
```

**Ожидаемый ответ:**
```json
{"status":"ok","agent_connected":true}
```

### Управление контейнером

```bash
# Остановить
docker-compose stop

# Запустить
docker-compose start

# Перезапустить
docker-compose restart

# Полная остановка и удаление
docker-compose down

# Пересборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Просмотр последних 100 строк
docker-compose logs --tail=100
```

### Обновление Relay

```bash
cd /opt/home-alice/relay
git pull
docker-compose up -d --build
docker-compose logs -f
```

### Устранение неполадок

**Agent не подключается:**
```bash
# Проверить логи relay
docker-compose logs -f

# Проверить что API_KEY совпадает
cat .env
# Сравнить с agent/config.yaml на Windows
```

**502 Bad Gateway в NPM:**
```bash
# Проверить что контейнер запущен
docker-compose ps

# Проверить health check
docker exec home-alice-relay wget -qO- http://localhost:8080/health
```

**WebSocket disconnects:**
```bash
# Проверить WebSocket Support включен в NPM
# Проверить логи
docker-compose logs -f | grep -i websocket
```

### Backup

```bash
# Backup .env файла (содержит API_KEY)
cp relay/.env relay/.env.backup

# Restore
cp relay/.env.backup relay/.env
docker-compose restart
```

---
```

**Step 3: Verify section added**

Run: `grep -A 5 "Вариант 3: Docker" DEPLOYMENT.md`
Expected: New section appears in file

**Step 4: Commit**

```bash
git add DEPLOYMENT.md
git commit -m "docs: add Docker deployment instructions to DEPLOYMENT.md"
```

---

## Task 7: Local testing

**Files:**
- Test: All created files

**Step 1: Create test .env**

```bash
cd relay
cat > .env <<EOF
API_KEY=test-key-for-local-testing
LISTEN_ADDR=:8080
EOF
```

**Step 2: Build image locally**

Run: `docker-compose build`
Expected: Build completes, shows multi-stage progress

**Step 3: Start container (without NPM network)**

Temporarily modify docker-compose.yml to remove external network requirement:
```bash
# Comment out networks section
docker-compose up -d
```

**Step 4: Test health endpoint**

Run: `curl http://localhost:8080/health`
Expected: `{"status":"ok","agent_connected":false}`

**Step 5: Check logs**

Run: `docker-compose logs`
Expected: Relay started on :8080 message

**Step 6: Stop and clean up**

```bash
docker-compose down
# Restore original docker-compose.yml
git checkout relay/docker-compose.yml
rm relay/.env
```

**Step 7: Document test results**

Create verification note that local build works.

---

## Task 8: Final verification and commit

**Files:**
- Verify: All created files

**Step 1: Verify all files created**

Run:
```bash
ls -la relay/.dockerignore
ls -la relay/Dockerfile
ls -la relay/docker-compose.yml
ls -la relay/.env.example
ls -la relay/.gitignore
grep -q "Вариант 3: Docker" DEPLOYMENT.md && echo "DEPLOYMENT.md updated"
```

Expected: All files exist

**Step 2: Verify git status**

Run: `git status`
Expected: All changes committed, working tree clean

**Step 3: Review commit history**

Run: `git log --oneline -7`
Expected: See all Docker-related commits

**Step 4: Tag release (optional)**

```bash
git tag -a v2.1.0-docker -m "Add Docker containerization support"
git push origin v2.1.0-docker
```

---

## Post-Implementation: VPS Deployment Checklist

After implementation complete, perform actual VPS deployment:

1. ✅ SSH to VPS
2. ✅ Clone/pull repository
3. ✅ Create .env with real API_KEY
4. ✅ Verify nginx_default network exists
5. ✅ Run `docker-compose up -d --build`
6. ✅ Check health endpoint from VPS
7. ✅ Configure NPM proxy host with SSL
8. ✅ Update Agent config.yaml on Windows PC
9. ✅ Start Agent and verify connection
10. ✅ Test end-to-end with Alice command

---

## Success Criteria

- ✅ Dockerfile builds successfully with multi-stage approach
- ✅ Final image size < 20MB
- ✅ docker-compose.yml validates and runs
- ✅ Health endpoint returns correct JSON
- ✅ Container auto-restarts on failure
- ✅ .env.example provides clear template
- ✅ DEPLOYMENT.md has complete Docker instructions
- ✅ All files committed to git
- ✅ Local testing passes
- ✅ (Post-deployment) Agent connects via NPM → Relay → Agent flow

---

## Rollback Plan

If deployment fails:

```bash
# Stop Docker deployment
cd /opt/home-alice/relay
docker-compose down

# Fall back to systemd service (from DEPLOYMENT.md Вариант 1)
sudo systemctl start home-alice-relay
```
