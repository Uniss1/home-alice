# VPS Deployment with Nginx Proxy Manager - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy Home Alice Go relay server on VPS behind Nginx Proxy Manager with SSL termination.

**Architecture:** Relay runs on localhost:8080 without TLS, NPM handles all external HTTPS traffic and SSL certificate management, WebSocket connections proxied through NPM.

**Tech Stack:** Go relay binary, systemd, Nginx Proxy Manager, Let's Encrypt SSL

---

## Prerequisites

Before starting:
- VPS running Ubuntu/Debian
- SSH access to VPS
- Domain name configured and pointing to VPS IP
- Nginx Proxy Manager installed and accessible

Required information:
- VPS SSH credentials: `user@vps-ip`
- Domain name: `your-domain.com`
- NPM web interface: `http://vps-ip:81`

---

## Task 1: Prepare Relay Binary on Local Machine

**Files:**
- Source: `/home/dmin/projects/home_alice/relay/relay-linux-amd64`

**Step 1: Verify relay binary exists locally**

```bash
ls -lh /home/dmin/projects/home_alice/relay/relay-linux-amd64
```

Expected output: Binary file approximately 7-8MB

**Step 2: Test SSH connection to VPS**

```bash
ssh user@vps-ip
```

Expected: Successfully connect to VPS shell

**Step 3: Exit VPS shell**

```bash
exit
```

---

## Task 2: Upload Binary and Create Directory Structure

**Files:**
- Create: `/home/<vps-user>/home-alice/relay/` (on VPS)

**Step 1: Create directory on VPS**

```bash
ssh user@vps-ip 'mkdir -p ~/home-alice/relay'
```

Expected: Directory created without errors

**Step 2: Upload relay binary to VPS**

```bash
scp /home/dmin/projects/home_alice/relay/relay-linux-amd64 user@vps-ip:~/home-alice/relay/relay
```

Expected output:
```
relay-linux-amd64    100%  7.2MB   1.2MB/s   00:06
```

**Step 3: Verify upload and set permissions**

```bash
ssh user@vps-ip 'chmod +x ~/home-alice/relay/relay && ls -lh ~/home-alice/relay/relay'
```

Expected output: File with execute permissions (`-rwxr-xr-x`)

**Step 4: Test relay binary execution**

```bash
ssh user@vps-ip '~/home-alice/relay/relay --help 2>&1 || echo "Binary requires environment variables"'
```

Expected: Binary runs (may show error about missing API_KEY - that's OK)

---

## Task 3: Generate API Key

**Step 1: Generate secure random API key**

```bash
ssh user@vps-ip 'openssl rand -hex 32'
```

Expected output: 64-character hex string like:
```
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

**Step 2: Save API key to local file for reference**

```bash
ssh user@vps-ip 'openssl rand -hex 32' > /tmp/home-alice-api-key.txt
cat /tmp/home-alice-api-key.txt
```

**Step 3: Verify key was saved**

```bash
cat /tmp/home-alice-api-key.txt
```

Expected: Display the generated API key

**Important:** You will need this API key for:
- Systemd service configuration (next task)
- Windows PC agent configuration (later)

---

## Task 4: Create and Configure systemd Service

**Files:**
- Create: `/etc/systemd/system/home-alice-relay.service` (on VPS)

**Step 1: Create systemd service file**

Replace `<vps-user>` with actual VPS username and `<api-key>` with the generated key from Task 3.

```bash
ssh user@vps-ip 'sudo tee /etc/systemd/system/home-alice-relay.service > /dev/null << "EOF"
[Unit]
Description=Home Alice Relay Server
After=network.target

[Service]
Type=simple
User=<vps-user>
WorkingDirectory=/home/<vps-user>/home-alice/relay
Environment="LISTEN_ADDR=127.0.0.1:8080"
Environment="API_KEY=<api-key>"
ExecStart=/home/<vps-user>/home-alice/relay/relay
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
'
```

Expected: Service file created without errors

**Step 2: Verify service file was created**

```bash
ssh user@vps-ip 'sudo cat /etc/systemd/system/home-alice-relay.service'
```

Expected output: Display the service file content with correct paths and API key

**Step 3: Reload systemd daemon**

```bash
ssh user@vps-ip 'sudo systemctl daemon-reload'
```

Expected: No output (silent success)

**Step 4: Enable service for auto-start**

```bash
ssh user@vps-ip 'sudo systemctl enable home-alice-relay'
```

Expected output:
```
Created symlink /etc/systemd/system/multi-user.target.wants/home-alice-relay.service → /etc/systemd/system/home-alice-relay.service
```

**Step 5: Verify service is enabled**

```bash
ssh user@vps-ip 'sudo systemctl is-enabled home-alice-relay'
```

Expected output: `enabled`

---

## Task 5: Start Relay Service and Verify

**Step 1: Start the relay service**

```bash
ssh user@vps-ip 'sudo systemctl start home-alice-relay'
```

Expected: No output (silent success)

**Step 2: Check service status**

```bash
ssh user@vps-ip 'sudo systemctl status home-alice-relay'
```

Expected output:
```
● home-alice-relay.service - Home Alice Relay Server
     Loaded: loaded (/etc/systemd/system/home-alice-relay.service; enabled)
     Active: active (running) since ...
```

**Step 3: View service logs**

```bash
ssh user@vps-ip 'sudo journalctl -u home-alice-relay -n 20 --no-pager'
```

Expected output should include:
```
Starting Home Alice Relay Server...
Listening on 127.0.0.1:8080
```

**Step 4: Test health endpoint locally on VPS**

```bash
ssh user@vps-ip 'curl -s http://localhost:8080/health'
```

Expected output:
```json
{"status":"ok","agent_connected":false}
```

**Step 5: Verify process is running**

```bash
ssh user@vps-ip 'ps aux | grep relay | grep -v grep'
```

Expected output: Process running as configured user

---

## Task 6: Configure Nginx Proxy Manager

**Important:** This task is performed through NPM web interface at `http://vps-ip:81`

**Step 1: Login to NPM web interface**

1. Open browser: `http://vps-ip:81`
2. Default credentials (if first time):
   - Email: `admin@example.com`
   - Password: `changeme`
3. Change password if prompted

**Step 2: Create Proxy Host**

1. Navigate to: **Hosts** → **Proxy Hosts**
2. Click: **Add Proxy Host**

**Step 3: Configure Details tab**

Fill in the following:

| Field | Value |
|-------|-------|
| Domain Names | `your-domain.com` |
| Scheme | `http` |
| Forward Hostname/IP | `127.0.0.1` |
| Forward Port | `8080` |
| Cache Assets | ☐ (unchecked) |
| Block Common Exploits | ☑ (checked) |
| Websockets Support | ☑ (checked) ← **IMPORTANT** |
| Access List | - (none) |

**Step 4: Configure SSL tab**

1. Select: **SSL Certificate** → **Request a new SSL Certificate**
2. Fill in:
   - ☑ Force SSL
   - ☑ HTTP/2 Support
   - ☑ HSTS Enabled
   - Email address: `your-email@example.com`
   - ☑ I Agree to the Let's Encrypt Terms of Service
3. Click: **Save**

**Step 5: Add Custom Nginx Configuration**

After saving, edit the same Proxy Host:

1. Go to **Advanced** tab
2. Add to **Custom Nginx Configuration**:

```nginx
# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";

# Timeouts for WebSocket
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

3. Click: **Save**

**Step 6: Verify SSL certificate was issued**

1. Go to: **SSL Certificates**
2. Verify: Certificate for `your-domain.com` shows status **Active**
3. Check expiry date (should be ~90 days from now)

---

## Task 7: External Testing and Verification

**Step 1: Test health endpoint via domain (external)**

From local machine:

```bash
curl -s https://your-domain.com/health
```

Expected output:
```json
{"status":"ok","agent_connected":false}
```

**Step 2: Test SSL certificate**

```bash
curl -vI https://your-domain.com/health 2>&1 | grep -E 'SSL|subject|issuer'
```

Expected output should include:
```
SSL connection using TLSv1.3
issuer: C=US; O=Let's Encrypt
subject: CN=your-domain.com
```

**Step 3: Test WebSocket endpoint accessibility**

```bash
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" https://your-domain.com/ws
```

Expected output:
```
HTTP/1.1 426 Upgrade Required
```

This is correct - relay requires proper WebSocket handshake with API key.

**Step 4: Verify relay logs show NPM connections**

```bash
ssh user@vps-ip 'sudo journalctl -u home-alice-relay -n 10 --no-pager'
```

Logs should show recent health check requests from NPM proxy.

---

## Task 8: Test Service Auto-Restart

**Step 1: Stop relay service manually**

```bash
ssh user@vps-ip 'sudo systemctl stop home-alice-relay'
```

**Step 2: Wait 6 seconds (RestartSec=5)**

```bash
sleep 6
```

**Step 3: Check service status**

```bash
ssh user@vps-ip 'sudo systemctl status home-alice-relay'
```

Expected output: Service should be **active (running)** again (auto-restarted by systemd)

**Step 4: Test health endpoint still works**

```bash
curl -s https://your-domain.com/health
```

Expected output:
```json
{"status":"ok","agent_connected":false}
```

---

## Task 9: Test System Reboot Persistence

**Step 1: Reboot VPS**

```bash
ssh user@vps-ip 'sudo reboot'
```

**Step 2: Wait for VPS to reboot (30-60 seconds)**

```bash
sleep 45
```

**Step 3: Verify SSH is back**

```bash
ssh user@vps-ip 'uptime'
```

Expected output: Uptime should be very low (< 2 minutes)

**Step 4: Check relay service auto-started**

```bash
ssh user@vps-ip 'sudo systemctl status home-alice-relay'
```

Expected output: Service should be **active (running)**

**Step 5: Test health endpoint after reboot**

```bash
curl -s https://your-domain.com/health
```

Expected output:
```json
{"status":"ok","agent_connected":false}
```

---

## Task 10: Document Deployment Information

**Files:**
- Create: `/home/dmin/projects/home_alice/DEPLOYMENT_INFO.md`

**Step 1: Create deployment info document**

```bash
cat > /home/dmin/projects/home_alice/DEPLOYMENT_INFO.md << 'EOF'
# Home Alice Deployment Information

**Deployment Date:** 2026-02-14
**Status:** ✅ Deployed and verified

## VPS Information

- **Host:** your-domain.com
- **Relay URL:** https://your-domain.com
- **Health Check:** https://your-domain.com/health
- **WebSocket:** wss://your-domain.com/ws

## Service Details

- **Service Name:** home-alice-relay
- **Binary Location:** /home/<vps-user>/home-alice/relay/relay
- **Listening Address:** 127.0.0.1:8080
- **SSL:** Managed by Nginx Proxy Manager (Let's Encrypt)

## Management Commands

```bash
# Check service status
ssh user@vps-ip 'sudo systemctl status home-alice-relay'

# View logs (real-time)
ssh user@vps-ip 'sudo journalctl -u home-alice-relay -f'

# View logs (last 50 lines)
ssh user@vps-ip 'sudo journalctl -u home-alice-relay -n 50'

# Restart service
ssh user@vps-ip 'sudo systemctl restart home-alice-relay'

# Stop service
ssh user@vps-ip 'sudo systemctl stop home-alice-relay'

# Start service
ssh user@vps-ip 'sudo systemctl start home-alice-relay'
```

## Health Checks

```bash
# External health check
curl -s https://your-domain.com/health

# Expected response
{"status":"ok","agent_connected":false}

# After Windows agent connects
{"status":"ok","agent_connected":true}
```

## Next Steps

1. **Configure Yandex Dialogs:**
   - Webhook URL: `https://your-domain.com/alice/webhook`

2. **Configure Windows PC Agent:**
   - `server_url`: `wss://your-domain.com/ws`
   - `api_key`: `<same key from /tmp/home-alice-api-key.txt>`

## API Key

**Important:** API key is stored in:
- VPS: `/etc/systemd/system/home-alice-relay.service` (Environment variable)
- Local reference: `/tmp/home-alice-api-key.txt`

Keep this key secure - it's needed for Windows agent authentication.

## SSL Certificate

- **Managed by:** Nginx Proxy Manager
- **Issuer:** Let's Encrypt
- **Auto-renewal:** Yes (NPM handles automatically)
- **Expiry check:** NPM web interface → SSL Certificates

## Troubleshooting

### Service won't start
```bash
ssh user@vps-ip 'sudo journalctl -u home-alice-relay -n 50'
```

### Health check fails locally
```bash
ssh user@vps-ip 'curl -v http://localhost:8080/health'
```

### Health check fails externally
- Check NPM Proxy Host configuration
- Verify WebSocket Support is enabled
- Check SSL certificate status

### WebSocket connection issues
- Verify Custom Nginx Config is present in NPM
- Check relay logs for connection attempts
- Test with: `wscat -c wss://your-domain.com/ws`
EOF
```

**Step 2: Review deployment info**

```bash
cat /home/dmin/projects/home_alice/DEPLOYMENT_INFO.md
```

**Step 3: Commit deployment documentation**

```bash
cd /home/dmin/projects/home_alice
git add DEPLOYMENT_INFO.md
git commit -m "docs: add deployment information for VPS setup

Deployment completed successfully on 2026-02-14.
- Relay running on VPS behind Nginx Proxy Manager
- SSL managed by Let's Encrypt
- Service auto-starts on system boot
- Health endpoint verified working

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Success Criteria

After completing all tasks, verify:

- ✅ Relay service status: `active (running)`
- ✅ Health check works locally: `http://localhost:8080/health`
- ✅ Health check works externally: `https://your-domain.com/health`
- ✅ SSL certificate active (Let's Encrypt)
- ✅ Service auto-restarts after manual stop
- ✅ Service auto-starts after system reboot
- ✅ NPM proxy configuration correct
- ✅ WebSocket support enabled
- ✅ API key documented and secure
- ✅ Deployment info committed to git

## Next Steps After Deployment

1. **Test with Yandex Dialogs:**
   - Create skill at https://dialogs.yandex.ru/developer/
   - Set webhook: `https://your-domain.com/alice/webhook`
   - Test with "Алиса, ping"
   - Expected response: "pong"

2. **Connect Windows PC Agent:**
   - Configure `agent/config.yaml` with:
     - `server_url: wss://your-domain.com/ws`
     - `api_key: <from /tmp/home-alice-api-key.txt>`
   - Run: `python -m agent.main`
   - Verify `/health` shows: `"agent_connected": true`

3. **Test End-to-End:**
   - Say to Alice: "Алиса, [навык], переключи на Chrome"
   - Verify PC switches to Chrome window
   - Check relay logs for request flow

---

## Estimated Time

- Task 1-2: Preparation and upload (~5 min)
- Task 3-5: Service setup and start (~10 min)
- Task 6: NPM configuration (~10 min)
- Task 7-9: Testing and verification (~15 min)
- Task 10: Documentation (~5 min)

**Total: ~45 minutes**
