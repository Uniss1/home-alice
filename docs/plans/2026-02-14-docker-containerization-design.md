# Docker Containerization Design

**Date:** 2026-02-14
**Project:** Home Alice v2
**Scope:** Containerize Go Relay server with Nginx Proxy Manager integration

## Overview

Implement Docker containerization for the Go Relay server using multi-stage build approach. The Python Agent will remain on Windows PC without Docker due to Windows API dependencies (pywin32, pycaw).

## 1. Architecture

The system consists of three layers:

**External Layer (Internet):**
- Yandex Alice → HTTPS requests to domain (port 443)
- Windows PC Agent → WebSocket connection to same domain

**Proxy Layer (Nginx Proxy Manager):**
- Accepts HTTPS on port 443
- Manages SSL/TLS certificates (Let's Encrypt)
- Proxies requests to Docker network `nginx_default`
- Route: `your-domain.com` → `http://home-alice-relay:8080`

**Application Layer (Docker container):**
- Go Relay in container `home-alice-relay`
- Listens HTTP on port 8080 (inside Docker network)
- Connected to `nginx_default` network (external network)
- Restart policy: `unless-stopped`
- Health check: `/health` endpoint

**Diagram:**
```
Internet (HTTPS :443)
    ↓
Nginx Proxy Manager (nginx_default network)
    ↓
home-alice-relay:8080 (HTTP, internal)
    ↓ WebSocket
Windows PC Agent
```

## 2. Components

Creating the following files in `relay/` directory:

### 2.1 Dockerfile (multi-stage build)

**Stage 1 (builder):** base image `golang:1.22-alpine`
- Copies go.mod, go.sum
- Downloads dependencies (`go mod download`)
- Builds static binary with optimization flags

**Stage 2 (runtime):** base image `alpine:latest` (~5MB)
- Copies only compiled binary
- Installs CA certificates (for HTTPS calls)
- Creates unprivileged user `relay`
- EXPOSE 8080
- Health check: `wget --no-verbose --tries=1 --spider http://localhost:8080/health`

### 2.2 docker-compose.yml

- Service: `home-alice-relay`
- Build context: `.`
- Environment variables from `.env` file
- Port: `8080` (only inside Docker network, not exposed externally)
- Networks: `nginx_default` (external: true)
- Restart: `unless-stopped`
- Health check from Dockerfile

### 2.3 .env (git ignored)

```bash
API_KEY=<secret-key>
LISTEN_ADDR=:8080
```

### 2.4 .dockerignore

Excludes from build:
- `*.md`
- `relay-linux-amd64`
- `.git`
- Tests

### 2.5 DEPLOYMENT.md update

Add section "Option 3: Docker Deployment" with docker-compose instructions.

## 3. Data Flow

### Build and Startup

1. `docker-compose build` → Multi-stage build:
   - Builder stage: compiles Go binary with optimization
   - Runtime stage: creates minimal image (~10-15MB)
2. `docker-compose up -d` → Container startup:
   - Container connects to `nginx_default` network
   - Relay listens on `:8080` inside network
   - Health check verifies `/health` every 30 seconds

### Request from Yandex Alice

1. Alice → `https://your-domain.com/alice/webhook` (HTTPS :443)
2. NPM receives request, validates SSL
3. NPM proxies → `http://home-alice-relay:8080/alice/webhook`
4. Relay processes, sends command to Agent via WebSocket
5. Response flows back the same path

### WebSocket Connection from Agent

1. Windows PC Agent → `wss://your-domain.com/ws` (HTTPS :443)
2. NPM upgrades connection to WebSocket
3. NPM proxies → `ws://home-alice-relay:8080/ws` (HTTP WebSocket)
4. Relay maintains persistent WebSocket connection with Agent
5. Relay forwards commands and responses between Alice and Agent

### Health Monitoring

- NPM can use `http://home-alice-relay:8080/health` for checks
- Docker health check automatically restarts on failure
- Logs available via `docker-compose logs -f`

## 4. Configuration

### Environment Variables (.env file)

```bash
# API key for Agent authentication (must match Agent's config.yaml)
API_KEY=<generate with: openssl rand -hex 32>

# Listen address (inside container)
LISTEN_ADDR=:8080
```

### Nginx Proxy Manager Setup

1. Create new Proxy Host in NPM Web UI
2. **Domain Names:** `your-domain.com`
3. **Scheme:** `http` (inside Docker network)
4. **Forward Hostname/IP:** `home-alice-relay` (container name)
5. **Forward Port:** `8080`
6. **WebSocket Support:** ✅ enable (important!)
7. **SSL:** Request new Let's Encrypt certificate
8. **Force SSL:** ✅ enable

### Agent Configuration Update (on Windows PC)

Update `agent/config.yaml`:
```yaml
server_url: "wss://your-domain.com/ws"  # Through NPM
api_key: "<same API_KEY from .env>"
```

### Volumes

Not required - Relay is stateless, stores no data. All logs go to stdout/stderr (accessible via `docker logs`).

### Ports

- Relay listens on `:8080` only inside Docker network
- No need to expose ports externally (NPM proxies)
- NPM already listens on :443 for HTTPS

## 5. Error Handling & Monitoring

### Automatic Recovery

- **Docker restart policy:** `unless-stopped` - container auto-restarts on failure
- **Health check:** verifies `/health` every 30 seconds
  - 3 failed checks → container marked unhealthy → automatic restart
- **Agent reconnection:** Agent has built-in reconnection logic (5-second backoff)

### Logging

- All Relay logs go to stdout/stderr
- View: `docker-compose logs -f home-alice-relay`
- Filter by time: `docker-compose logs --since 1h`
- Docker automatically rotates logs (json-file driver)

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Agent won't connect | Invalid API_KEY | Verify match between .env and config.yaml |
| 502 Bad Gateway in NPM | Container not running | `docker-compose ps`, check logs |
| WebSocket disconnects | Health check failed | Check `/health` endpoint, container logs |
| NPM can't see container | Different Docker networks | Ensure both in `nginx_default` |

### Monitoring

- **Health check:** `curl http://localhost/health` (through NPM)
- **Container status:** `docker-compose ps`
- **Real-time logs:** `docker-compose logs -f`
- **Agent connection status:** health response shows `agent_connected: true/false`

### Disaster Recovery

- Container is stateless - can delete and recreate without data loss
- Backup only .env file (contains API_KEY)
- Rollback: `docker-compose down && git checkout previous-version && docker-compose up -d`

## 6. Deployment

### Initial Deployment (on VPS)

**1. Preparation:**
```bash
cd /opt
git clone https://github.com/yourusername/home-alice.git
cd home-alice/relay
```

**2. Create .env file:**
```bash
cat > .env <<EOF
API_KEY=$(openssl rand -hex 32)
LISTEN_ADDR=:8080
EOF

# Save API_KEY - needed for Agent
cat .env
```

**3. Connect to NPM network:**
```bash
# Verify nginx_default exists
docker network ls | grep nginx_default
```

**4. Start:**
```bash
docker-compose up -d --build
```

**5. Check status:**
```bash
docker-compose ps
docker-compose logs -f
# Should see: Relay started on :8080
```

**6. Configure NPM:**
- Open NPM UI (usually `http://vps-ip:81`)
- Create Proxy Host as described in Configuration section
- Obtain SSL certificate

**7. Update Agent config:**
- Copy API_KEY from .env
- Update `agent/config.yaml` on Windows PC
- Restart Agent

### Updates (when code changes)

```bash
cd /opt/home-alice/relay
git pull
docker-compose up -d --build
docker-compose logs -f
```

### Management Commands

```bash
# Stop
docker-compose stop

# Restart
docker-compose restart

# Full rebuild
docker-compose down
docker-compose up -d --build

# View logs
docker-compose logs -f --tail=100
```

### Verification

```bash
# 1. Health check
curl https://your-domain.com/health
# Expected: {"status":"ok","agent_connected":false}

# 2. After Agent connects
curl https://your-domain.com/health
# Expected: {"status":"ok","agent_connected":true}

# 3. Test via Alice
# Say: "Алиса, попроси Home Alice системная информация"
```

## Summary

This design provides:
- ✅ **Minimal footprint:** 10-15MB image vs 800MB
- ✅ **Security:** Unprivileged user, minimal dependencies
- ✅ **Reliability:** Auto-restart, health checks
- ✅ **Integration:** Seamless NPM connection
- ✅ **Maintainability:** Simple updates, clear logging
- ✅ **Production-ready:** Industry standard multi-stage build

## Next Steps

1. Create Dockerfile with multi-stage build
2. Create docker-compose.yml
3. Create .dockerignore
4. Update DEPLOYMENT.md with Docker instructions
5. Test local build
6. Deploy to VPS
7. Configure NPM
8. Verify end-to-end functionality
