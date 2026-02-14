# Home Alice v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Full voice control of a Windows PC via Yandex Alice — a minimal Go relay on VPS forwards voice text to a Python agent on the PC, which uses GLM-4 (free LLM with function calling) to interpret commands and execute them via system tools.

**Architecture:** Go-relay on VPS (webhook + WebSocket proxy, ~100 lines). Python agent on Windows with GLM-4 function calling and a full set of PC-control tools (windows, processes, browser, audio, keyboard, files).

**Tech Stack:** Go 1.22+ (relay), Python 3.11+ (agent), GLM-4 API via `openai` library, `pywin32`, `psutil`, `pycaw`, `pyautogui`, `websockets`

---

### Task 1: Go-relay — project setup

**Files:**
- Create: `relay/go.mod`
- Create: `relay/main.go`

**Step 1: Initialize Go module**

```bash
mkdir -p relay && cd relay && go mod init github.com/home-alice/relay
```

**Step 2: Add gorilla/websocket dependency**

```bash
cd relay && go get github.com/gorilla/websocket
```

**Step 3: Commit**

```bash
git add relay/go.mod relay/go.sum
git commit -m "chore(relay): init Go module with websocket dependency"
```

---

### Task 2: Go-relay — full implementation

**Files:**
- Create: `relay/main.go`

The entire relay is one file. It handles:
- Alice webhook (POST /alice/webhook)
- WebSocket for PC agent (GET /ws)
- Health check (GET /health)
- Ping/pong for Alice health checks
- API key authentication
- Timeout handling (4 sec)

**Step 1: Write the complete relay**

```go
// relay/main.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Alice protocol types
type AliceRequest struct {
	Request struct {
		Command           string `json:"command"`
		OriginalUtterance string `json:"original_utterance"`
		Type              string `json:"type"`
	} `json:"request"`
	Session struct {
		New       bool   `json:"new"`
		SessionID string `json:"session_id"`
		MessageID int    `json:"message_id"`
		SkillID   string `json:"skill_id"`
	} `json:"session"`
	Version string `json:"version"`
}

type AliceResponse struct {
	Response struct {
		Text       string `json:"text"`
		EndSession bool   `json:"end_session"`
	} `json:"response"`
	Version string `json:"version"`
}

// Agent connection
var (
	agentConn *websocket.Conn
	agentMu   sync.Mutex
	pending   = make(map[string]chan string) // messageID -> response channel
	pendingMu sync.Mutex
)

var upgrader = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func aliceResponse(text, version string) AliceResponse {
	resp := AliceResponse{Version: version}
	resp.Response.Text = text
	resp.Response.EndSession = false
	return resp
}

func handleAliceWebhook(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req AliceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	version := req.Version
	if version == "" {
		version = "1.0"
	}

	// Health check from Yandex
	if req.Request.OriginalUtterance == "ping" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse("pong", version))
		return
	}

	// New session greeting
	command := req.Request.Command
	if req.Session.New && command == "" {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse(
			"Привет! Я могу управлять твоим компьютером. Скажи, что нужно сделать.",
			version,
		))
		return
	}

	// Check agent connection
	agentMu.Lock()
	conn := agentConn
	agentMu.Unlock()

	if conn == nil {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse("Компьютер сейчас недоступен.", version))
		return
	}

	// Send command to agent and wait for response
	msgID := req.Session.SessionID + "-" + string(rune(req.Session.MessageID))
	respCh := make(chan string, 1)

	pendingMu.Lock()
	pending[msgID] = respCh
	pendingMu.Unlock()

	defer func() {
		pendingMu.Lock()
		delete(pending, msgID)
		pendingMu.Unlock()
	}()

	// Send to agent: {"id": "...", "text": "..."}
	msg, _ := json.Marshal(map[string]string{"id": msgID, "text": command})
	agentMu.Lock()
	err := agentConn.WriteMessage(websocket.TextMessage, msg)
	agentMu.Unlock()

	if err != nil {
		log.Printf("Failed to send to agent: %v", err)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse("Не удалось отправить команду на компьютер.", version))
		return
	}

	// Wait for response with timeout
	select {
	case text := <-respCh:
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse(text, version))
	case <-time.After(4 * time.Second):
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(aliceResponse("Команда принята, но компьютер не ответил вовремя.", version))
	}
}

func handleWS(w http.ResponseWriter, r *http.Request) {
	apiKey := getEnv("API_KEY", "")
	if apiKey != "" && r.URL.Query().Get("key") != apiKey {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade failed: %v", err)
		return
	}

	agentMu.Lock()
	if agentConn != nil {
		agentConn.Close()
	}
	agentConn = conn
	agentMu.Unlock()

	log.Println("PC agent connected")

	defer func() {
		agentMu.Lock()
		if agentConn == conn {
			agentConn = nil
		}
		agentMu.Unlock()
		conn.Close()
		log.Println("PC agent disconnected")
	}()

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			log.Printf("WebSocket read error: %v", err)
			return
		}

		// Parse response: {"id": "...", "text": "..."}
		var resp map[string]string
		if err := json.Unmarshal(message, &resp); err != nil {
			log.Printf("Invalid response from agent: %v", err)
			continue
		}

		msgID := resp["id"]
		text := resp["text"]

		pendingMu.Lock()
		ch, ok := pending[msgID]
		pendingMu.Unlock()

		if ok {
			ch <- text
		}
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	agentMu.Lock()
	connected := agentConn != nil
	agentMu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":          "ok",
		"agent_connected": connected,
	})
}

func main() {
	addr := getEnv("LISTEN_ADDR", ":8443")
	tlsCert := getEnv("TLS_CERT", "")
	tlsKey := getEnv("TLS_KEY", "")

	http.HandleFunc("/alice/webhook", handleAliceWebhook)
	http.HandleFunc("/ws", handleWS)
	http.HandleFunc("/health", handleHealth)

	log.Printf("Starting relay on %s", addr)

	if tlsCert != "" && tlsKey != "" {
		log.Fatal(http.ListenAndServeTLS(addr, tlsCert, tlsKey, nil))
	} else {
		log.Fatal(http.ListenAndServe(addr, nil))
	}
}
```

**Step 2: Build and verify it compiles**

```bash
cd relay && go build -o relay . && ls -lh relay
```
Expected: binary ~5-7MB

**Step 3: Commit**

```bash
git add relay/main.go
git commit -m "feat(relay): implement Go relay server with Alice webhook and WebSocket"
```

---

### Task 3: Agent — project scaffolding

**Files:**
- Create: `agent/requirements.txt`
- Create: `agent/config.example.yaml`
- Create: `agent/__init__.py`
- Create: `agent/tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/agent/__init__.py`
- Create: `tests/agent/tools/__init__.py`

**Step 1: Create requirements.txt**

```
websockets==14.1
openai==1.58.1
pyyaml==6.0.2
psutil==6.1.1
pyautogui==0.9.54
comtypes==1.4.8
pycaw==20240210
pywin32==308
httpx==0.27.0
```

**Step 2: Create config.example.yaml**

```yaml
server_url: "wss://your-vps.com/ws"
api_key: "your-secret-key"

llm:
  provider: "glm4"
  api_key: "your-glm4-api-key"
  base_url: "https://open.bigmodel.cn/api/paas/v4"
  model: "glm-4"

vk_token: ""

allowed_commands:
  - "ipconfig"
  - "systeminfo"
  - "tasklist"
```

**Step 3: Create `__init__.py` files and test directories**

Empty files for all `__init__.py`.

**Step 4: Create dev requirements**

```
requirements-dev.txt:
```
```
pytest==8.3.4
pytest-asyncio==0.25.0
```

**Step 5: Commit**

```bash
git add agent/ tests/ requirements-dev.txt
git commit -m "chore(agent): scaffold project structure and dependencies"
```

---

### Task 4: Agent — config module

**Files:**
- Create: `agent/config.py`
- Create: `tests/agent/test_config.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_config.py
import os
import tempfile
import yaml
from agent.config import load_config, AgentConfig


def test_load_config():
    data = {
        "server_url": "wss://example.com/ws",
        "api_key": "test-key",
        "llm": {
            "provider": "glm4",
            "api_key": "glm-key",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4",
        },
        "vk_token": "vk-token",
        "allowed_commands": ["ipconfig", "tasklist"],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = f.name
    try:
        config = load_config(path)
        assert isinstance(config, AgentConfig)
        assert config.server_url == "wss://example.com/ws"
        assert config.llm.model == "glm-4"
        assert config.allowed_commands == ["ipconfig", "tasklist"]
    finally:
        os.unlink(path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_config.py -v`

**Step 3: Write implementation**

```python
# agent/config.py
from dataclasses import dataclass, field
import yaml


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str


@dataclass
class AgentConfig:
    server_url: str
    api_key: str
    llm: LLMConfig
    vk_token: str = ""
    allowed_commands: list[str] = field(default_factory=list)


def load_config(path: str) -> AgentConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    llm_data = data["llm"]
    return AgentConfig(
        server_url=data["server_url"],
        api_key=data["api_key"],
        llm=LLMConfig(
            provider=llm_data["provider"],
            api_key=llm_data["api_key"],
            base_url=llm_data["base_url"],
            model=llm_data["model"],
        ),
        vk_token=data.get("vk_token", ""),
        allowed_commands=data.get("allowed_commands", []),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_config.py -v`

**Step 5: Commit**

```bash
git add agent/config.py tests/agent/test_config.py
git commit -m "feat(agent): add config module"
```

---

### Task 5: Agent — system tools (shutdown, reboot, sleep, system_info)

**Files:**
- Create: `agent/tools/system.py`
- Create: `tests/agent/tools/test_system.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_system.py
from unittest.mock import patch, MagicMock
from agent.tools.system import shutdown, reboot, sleep_pc, get_system_info


@patch("agent.tools.system.subprocess.run")
def test_shutdown(mock_run):
    result = shutdown()
    mock_run.assert_called_once_with(["shutdown", "/s", "/t", "0"], check=True)
    assert "выключаю" in result.lower() or "shutdown" in result.lower()


@patch("agent.tools.system.subprocess.run")
def test_reboot(mock_run):
    result = reboot()
    mock_run.assert_called_once_with(["shutdown", "/r", "/t", "0"], check=True)
    assert "перезагружаю" in result.lower() or "reboot" in result.lower()


@patch("agent.tools.system.subprocess.run")
def test_sleep_pc(mock_run):
    result = sleep_pc()
    assert mock_run.called


@patch("agent.tools.system.psutil")
def test_get_system_info(mock_psutil):
    mock_psutil.cpu_percent.return_value = 25.0
    mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0, total=16 * 1024**3)
    mock_psutil.disk_usage.return_value = MagicMock(percent=45.0, total=500 * 1024**3)
    result = get_system_info()
    assert "CPU" in result or "cpu" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/tools/test_system.py -v`

**Step 3: Write implementation**

```python
# agent/tools/system.py
import subprocess
import logging
import psutil

logger = logging.getLogger(__name__)


def shutdown() -> str:
    try:
        subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
        return "Выключаю компьютер"
    except Exception as e:
        return f"Ошибка при выключении: {e}"


def reboot() -> str:
    try:
        subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
        return "Перезагружаю компьютер"
    except Exception as e:
        return f"Ошибка при перезагрузке: {e}"


def sleep_pc() -> str:
    try:
        subprocess.run(
            ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True
        )
        return "Перевожу в спящий режим"
    except Exception as e:
        return f"Ошибка: {e}"


def get_system_info() -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (
            f"CPU: {cpu}%, "
            f"RAM: {mem.percent}% ({mem.total // (1024**3)} GB), "
            f"Диск: {disk.percent}% ({disk.total // (1024**3)} GB)"
        )
    except Exception as e:
        return f"Ошибка: {e}"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/system.py tests/agent/tools/test_system.py
git commit -m "feat(agent): add system tools (shutdown, reboot, sleep, info)"
```

---

### Task 6: Agent — window management tools

**Files:**
- Create: `agent/tools/windows.py`
- Create: `tests/agent/tools/test_windows.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_windows.py
from unittest.mock import patch, MagicMock
from agent.tools.windows import list_windows, switch_window, close_window


@patch("agent.tools.windows.win32gui")
def test_list_windows(mock_gui):
    # EnumWindows calls callback for each window
    def fake_enum(callback, _):
        callback(1001, None)
        callback(1002, None)

    mock_gui.EnumWindows.side_effect = fake_enum
    mock_gui.IsWindowVisible.return_value = True
    mock_gui.GetWindowText.side_effect = lambda h: "Chrome" if h == 1001 else "VS Code"

    result = list_windows()
    assert "Chrome" in result
    assert "VS Code" in result


@patch("agent.tools.windows.win32gui")
def test_switch_window(mock_gui):
    def fake_enum(callback, _):
        callback(1001, None)

    mock_gui.EnumWindows.side_effect = fake_enum
    mock_gui.IsWindowVisible.return_value = True
    mock_gui.GetWindowText.return_value = "Google Chrome"

    result = switch_window("chrome")
    assert "Chrome" in result or "переключил" in result.lower()


@patch("agent.tools.windows.win32gui")
def test_switch_window_not_found(mock_gui):
    mock_gui.EnumWindows.side_effect = lambda cb, _: None
    result = switch_window("несуществующее")
    assert "не найдено" in result.lower() or "not found" in result.lower()
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# agent/tools/windows.py
import logging

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

logger = logging.getLogger(__name__)


def _get_visible_windows() -> list[tuple[int, str]]:
    if not win32gui:
        return []
    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                windows.append((hwnd, title))

    win32gui.EnumWindows(callback, None)
    return windows


def list_windows() -> str:
    windows = _get_visible_windows()
    if not windows:
        return "Нет открытых окон"
    lines = [f"- {title}" for _, title in windows]
    return "Открытые окна:\n" + "\n".join(lines)


def switch_window(title: str) -> str:
    windows = _get_visible_windows()
    title_lower = title.lower()
    for hwnd, wnd_title in windows:
        if title_lower in wnd_title.lower():
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
                return f"Переключил на «{wnd_title}»"
            except Exception as e:
                return f"Ошибка при переключении: {e}"
    return f"Окно «{title}» не найдено"


def close_window(title: str) -> str:
    windows = _get_visible_windows()
    title_lower = title.lower()
    for hwnd, wnd_title in windows:
        if title_lower in wnd_title.lower():
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return f"Закрыл «{wnd_title}»"
            except Exception as e:
                return f"Ошибка: {e}"
    return f"Окно «{title}» не найдено"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/windows.py tests/agent/tools/test_windows.py
git commit -m "feat(agent): add window management tools"
```

---

### Task 7: Agent — browser tools (open_url, search_vk_video)

**Files:**
- Create: `agent/tools/browser.py`
- Create: `tests/agent/tools/test_browser.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_browser.py
from unittest.mock import patch, MagicMock
from agent.tools.browser import open_url, search_vk_video


@patch("agent.tools.browser.webbrowser.open")
def test_open_url(mock_open):
    result = open_url("https://vk.com/video123")
    mock_open.assert_called_once_with("https://vk.com/video123")
    assert "открываю" in result.lower() or "open" in result.lower()


@patch("agent.tools.browser.webbrowser.open", side_effect=Exception("No browser"))
def test_open_url_failure(mock_open):
    result = open_url("https://example.com")
    assert "ошибка" in result.lower() or "error" in result.lower()


@patch("agent.tools.browser.httpx.Client")
def test_search_vk_video(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": {
            "count": 1,
            "items": [{"id": 456, "owner_id": -123, "title": "Test", "views": 1000}],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.get = MagicMock(return_value=mock_response)

    result = search_vk_video("котики", vk_token="test-token")
    assert "vk.com" in result
```

**Step 2: Run test**

**Step 3: Write implementation**

```python
# agent/tools/browser.py
import webbrowser
import logging
import httpx

logger = logging.getLogger(__name__)


def open_url(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"Открываю {url}"
    except Exception as e:
        return f"Ошибка при открытии URL: {e}"


def search_vk_video(query: str, vk_token: str, channel_id: int | None = None) -> str:
    params = {
        "q": query,
        "access_token": vk_token,
        "v": "5.199",
        "count": 10,
        "sort": 2,
    }
    if channel_id:
        params["owner_id"] = channel_id

    try:
        with httpx.Client() as client:
            resp = client.get(
                "https://api.vk.com/method/video.search",
                params=params,
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("response", {}).get("items", [])
        if not items:
            return f"Не нашла видео по запросу «{query}»"

        best = max(items, key=lambda v: v.get("views", 0))
        url = f"https://vk.com/video{best['owner_id']}_{best['id']}"
        webbrowser.open(url)
        return f"Включаю «{best.get('title', query)}»"
    except Exception as e:
        return f"Ошибка поиска видео: {e}"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/browser.py tests/agent/tools/test_browser.py
git commit -m "feat(agent): add browser tools (open_url, search_vk_video)"
```

---

### Task 8: Agent — audio tools (volume)

**Files:**
- Create: `agent/tools/audio.py`
- Create: `tests/agent/tools/test_audio.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_audio.py
from unittest.mock import patch, MagicMock
from agent.tools.audio import volume_set, volume_mute


@patch("agent.tools.audio._get_volume_interface")
def test_volume_set(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    result = volume_set(75)
    mock_vol.SetMasterVolumeLevelScalar.assert_called_once_with(0.75, None)
    assert "75" in result


@patch("agent.tools.audio._get_volume_interface")
def test_volume_mute(mock_iface):
    mock_vol = MagicMock()
    mock_iface.return_value = mock_vol
    result = volume_mute(True)
    mock_vol.SetMute.assert_called_once_with(1, None)
```

**Step 2: Run test**

**Step 3: Write implementation**

```python
# agent/tools/audio.py
import logging

logger = logging.getLogger(__name__)


def _get_volume_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def volume_set(level: int) -> str:
    try:
        vol = _get_volume_interface()
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
        return f"Громкость: {level}%"
    except Exception as e:
        return f"Ошибка: {e}"


def volume_mute(mute: bool) -> str:
    try:
        vol = _get_volume_interface()
        vol.SetMute(1 if mute else 0, None)
        return "Звук выключен" if mute else "Звук включён"
    except Exception as e:
        return f"Ошибка: {e}"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/audio.py tests/agent/tools/test_audio.py
git commit -m "feat(agent): add audio tools (volume control)"
```

---

### Task 9: Agent — keyboard tools

**Files:**
- Create: `agent/tools/keyboard.py`
- Create: `tests/agent/tools/test_keyboard.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_keyboard.py
from unittest.mock import patch
from agent.tools.keyboard import press_keys, type_text


@patch("agent.tools.keyboard.pyautogui.hotkey")
def test_press_keys(mock_hotkey):
    result = press_keys(["ctrl", "c"])
    mock_hotkey.assert_called_once_with("ctrl", "c")
    assert "нажал" in result.lower() or "pressed" in result.lower()


@patch("agent.tools.keyboard.pyautogui.write")
def test_type_text(mock_write):
    result = type_text("hello world")
    mock_write.assert_called_once_with("hello world", interval=0.02)
```

**Step 2: Run test**

**Step 3: Write implementation**

```python
# agent/tools/keyboard.py
import logging
import pyautogui

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE = False


def press_keys(keys: list[str]) -> str:
    try:
        pyautogui.hotkey(*keys)
        return f"Нажал {'+'.join(keys)}"
    except Exception as e:
        return f"Ошибка: {e}"


def type_text(text: str) -> str:
    try:
        pyautogui.write(text, interval=0.02)
        return f"Напечатал текст"
    except Exception as e:
        return f"Ошибка: {e}"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/keyboard.py tests/agent/tools/test_keyboard.py
git commit -m "feat(agent): add keyboard tools (hotkeys, typing)"
```

---

### Task 10: Agent — process tools

**Files:**
- Create: `agent/tools/process.py`
- Create: `tests/agent/tools/test_process.py`

**Step 1: Write the failing test**

```python
# tests/agent/tools/test_process.py
from unittest.mock import patch, MagicMock
from agent.tools.process import list_processes, kill_process


@patch("agent.tools.process.psutil.process_iter")
def test_list_processes(mock_iter):
    proc1 = MagicMock()
    proc1.info = {"pid": 1, "name": "chrome.exe", "cpu_percent": 5.0}
    proc2 = MagicMock()
    proc2.info = {"pid": 2, "name": "code.exe", "cpu_percent": 3.0}
    mock_iter.return_value = [proc1, proc2]

    result = list_processes()
    assert "chrome" in result.lower()


@patch("agent.tools.process.psutil.Process")
def test_kill_process(mock_proc_cls):
    mock_proc = MagicMock()
    mock_proc.name.return_value = "notepad.exe"
    mock_proc_cls.return_value = mock_proc

    result = kill_process(1234)
    mock_proc.kill.assert_called_once()
```

**Step 2: Run test**

**Step 3: Write implementation**

```python
# agent/tools/process.py
import logging
import psutil

logger = logging.getLogger(__name__)


def list_processes(top_n: int = 15) -> str:
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            procs.append(p.info)
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
        lines = [
            f"  {p['name']} (PID {p['pid']}, CPU {p.get('cpu_percent', 0):.1f}%)"
            for p in procs[:top_n]
        ]
        return "Топ процессов:\n" + "\n".join(lines)
    except Exception as e:
        return f"Ошибка: {e}"


def kill_process(pid: int) -> str:
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.kill()
        return f"Завершил процесс {name} (PID {pid})"
    except psutil.NoSuchProcess:
        return f"Процесс с PID {pid} не найден"
    except Exception as e:
        return f"Ошибка: {e}"
```

**Step 4: Run test, step 5: Commit**

```bash
git add agent/tools/process.py tests/agent/tools/test_process.py
git commit -m "feat(agent): add process management tools"
```

---

### Task 11: Agent — LLM client with function calling

**Files:**
- Create: `agent/llm_client.py`
- Create: `agent/tool_executor.py`
- Create: `tests/agent/test_llm_client.py`

This is the core — ties LLM function calling to tool execution.

**Step 1: Write the failing test**

```python
# tests/agent/test_llm_client.py
from unittest.mock import patch, MagicMock
import pytest
from agent.llm_client import LLMClient
from agent.config import LLMConfig


@pytest.fixture
def llm_config():
    return LLMConfig(
        provider="glm4",
        api_key="test-key",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4",
    )


def test_get_tool_definitions(llm_config):
    client = LLMClient(llm_config, vk_token="", allowed_commands=[])
    tools = client.get_tool_definitions()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Each tool should have type, function with name, description, parameters
    for tool in tools:
        assert tool["type"] == "function"
        assert "name" in tool["function"]
        assert "description" in tool["function"]


def test_tool_executor_shutdown(llm_config):
    from agent.tool_executor import ToolExecutor
    executor = ToolExecutor(vk_token="", allowed_commands=[])
    with patch("agent.tools.system.subprocess.run"):
        result = executor.execute("shutdown", {})
    assert isinstance(result, str)
```

**Step 2: Run test**

**Step 3: Write tool_executor.py**

```python
# agent/tool_executor.py
import logging
from agent.tools.system import shutdown, reboot, sleep_pc, get_system_info
from agent.tools.windows import list_windows, switch_window, close_window
from agent.tools.browser import open_url, search_vk_video
from agent.tools.audio import volume_set, volume_mute
from agent.tools.keyboard import press_keys, type_text
from agent.tools.process import list_processes, kill_process

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, vk_token: str = "", allowed_commands: list[str] | None = None):
        self.vk_token = vk_token
        self.allowed_commands = allowed_commands or []

    def execute(self, tool_name: str, args: dict) -> str:
        try:
            match tool_name:
                case "shutdown":
                    return shutdown()
                case "reboot":
                    return reboot()
                case "sleep_pc":
                    return sleep_pc()
                case "get_system_info":
                    return get_system_info()
                case "list_windows":
                    return list_windows()
                case "switch_window":
                    return switch_window(args.get("title", ""))
                case "close_window":
                    return close_window(args.get("title", ""))
                case "open_url":
                    return open_url(args.get("url", ""))
                case "search_vk_video":
                    return search_vk_video(
                        args.get("query", ""),
                        self.vk_token,
                        args.get("channel_id"),
                    )
                case "volume_set":
                    return volume_set(args.get("level", 50))
                case "volume_mute":
                    return volume_mute(args.get("mute", True))
                case "press_keys":
                    return press_keys(args.get("keys", []))
                case "type_text":
                    return type_text(args.get("text", ""))
                case "list_processes":
                    return list_processes(args.get("top_n", 15))
                case "kill_process":
                    return kill_process(args.get("pid", 0))
                case "run_command":
                    cmd = args.get("command", "")
                    if cmd.split()[0] not in self.allowed_commands:
                        return f"Команда «{cmd}» не в белом списке"
                    import subprocess
                    result = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=10
                    )
                    return result.stdout or result.stderr or "Выполнено"
                case _:
                    return f"Неизвестный инструмент: {tool_name}"
        except Exception as e:
            logger.error("Tool execution error: %s", e)
            return f"Ошибка: {e}"
```

**Step 4: Write llm_client.py**

```python
# agent/llm_client.py
import json
import logging
from openai import OpenAI
from agent.config import LLMConfig
from agent.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — AI-агент для управления домашним компьютером через голосовые команды.
Пользователь говорит команду голосом через Алису, ты получаешь текст и выполняешь действия.

Правила:
- Выполняй команду, используя доступные инструменты
- Можешь вызывать несколько инструментов подряд если нужно
- Отвечай кратко — твой ответ будет озвучен Алисой (макс 1-2 предложения)
- Отвечай на русском языке"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "shutdown",
            "description": "Выключить компьютер",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reboot",
            "description": "Перезагрузить компьютер",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep_pc",
            "description": "Перевести компьютер в спящий режим",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Получить информацию о системе (CPU, RAM, диск)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_windows",
            "description": "Показать список открытых окон",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_window",
            "description": "Переключиться на окно по части заголовка",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Часть заголовка окна (например 'Chrome', 'VS Code')"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_window",
            "description": "Закрыть окно по части заголовка",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Часть заголовка окна"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Открыть URL в браузере",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL для открытия"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vk_video",
            "description": "Найти и открыть видео на VK Video по запросу (самое популярное)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "channel_id": {"type": "integer", "description": "ID канала VK (опционально)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_set",
            "description": "Установить громкость от 0 до 100",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Уровень громкости (0-100)"},
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_mute",
            "description": "Включить или выключить звук (mute)",
            "parameters": {
                "type": "object",
                "properties": {
                    "mute": {"type": "boolean", "description": "true — выключить звук, false — включить"},
                },
                "required": ["mute"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_keys",
            "description": "Нажать комбинацию клавиш (горячие клавиши)",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список клавиш (например ['ctrl', 'c'], ['alt', 'tab'])",
                    },
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Напечатать текст на клавиатуре",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст для ввода"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Показать список запущенных процессов (топ по CPU)",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Сколько процессов показать (по умолчанию 15)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kill_process",
            "description": "Завершить процесс по PID",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "ID процесса"},
                },
                "required": ["pid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Выполнить системную команду (только из белого списка)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Команда для выполнения"},
                },
                "required": ["command"],
            },
        },
    },
]


class LLMClient:
    def __init__(self, config: LLMConfig, vk_token: str = "", allowed_commands: list[str] | None = None):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model = config.model
        self.executor = ToolExecutor(vk_token=vk_token, allowed_commands=allowed_commands)

    def get_tool_definitions(self) -> list[dict]:
        return TOOL_DEFINITIONS

    def process_command(self, user_text: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        try:
            # Up to 3 rounds of tool calls
            for _ in range(3):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )

                choice = response.choices[0]

                # If no tool calls — return the text response
                if not choice.message.tool_calls:
                    return choice.message.content or "Готово"

                # Execute tool calls
                messages.append(choice.message)
                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    logger.info("Calling tool: %s(%s)", fn_name, fn_args)
                    result = self.executor.execute(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            # If we exhausted rounds, get final response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or "Готово"

        except Exception as e:
            logger.error("LLM error: %s", e)
            return f"Не удалось обработать команду: {e}"
```

**Step 5: Run test, step 6: Commit**

```bash
git add agent/llm_client.py agent/tool_executor.py tests/agent/test_llm_client.py
git commit -m "feat(agent): add LLM client with function calling and tool executor"
```

---

### Task 12: Agent — main.py (WebSocket client + entry point)

**Files:**
- Create: `agent/main.py`

**Step 1: Write implementation**

```python
# agent/main.py
import asyncio
import json
import logging
import os
import websockets
from agent.config import load_config
from agent.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_agent(config_path: str):
    config = load_config(config_path)
    llm = LLMClient(
        config=config.llm,
        vk_token=config.vk_token,
        allowed_commands=config.allowed_commands,
    )
    url = f"{config.server_url}?key={config.api_key}"

    while True:
        try:
            logger.info("Connecting to %s", config.server_url)
            async with websockets.connect(url) as ws:
                logger.info("Connected to relay server")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg_id = data.get("id", "")
                        text = data.get("text", "")
                        logger.info("Received command: %s", text)

                        # Process via LLM (runs in thread to not block)
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None, llm.process_command, text
                        )
                        logger.info("Result: %s", result)

                        # Send response back
                        response = json.dumps({"id": msg_id, "text": result})
                        await ws.send(response)

                    except Exception as e:
                        logger.error("Error processing message: %s", e)
                        try:
                            error_resp = json.dumps({
                                "id": data.get("id", ""),
                                "text": f"Ошибка: {e}",
                            })
                            await ws.send(error_resp)
                        except Exception:
                            pass

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning("Connection lost: %s. Reconnecting in 5s...", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("Unexpected error: %s. Reconnecting in 5s...", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    config_file = os.environ.get("CONFIG_PATH", "agent/config.yaml")
    asyncio.run(run_agent(config_file))
```

**Step 2: Commit**

```bash
git add agent/main.py
git commit -m "feat(agent): add main entry point with WebSocket client and LLM integration"
```

---

### Task 13: Run all tests and final verification

**Step 1: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: ALL PASS

**Step 2: Build Go relay**

```bash
cd relay && go build -o relay .
```

Expected: binary compiled, ~5-7MB

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify all tests pass, project complete"
```

---

## Deployment Notes

### VPS (Go relay)

```bash
# Build
cd relay && GOOS=linux GOARCH=amd64 go build -o relay .

# Copy to VPS
scp relay user@vps:/opt/home-alice/

# On VPS: run with env vars
API_KEY=your-secret-key LISTEN_ADDR=:8443 TLS_CERT=cert.pem TLS_KEY=key.pem /opt/home-alice/relay

# Or use systemd service
```

### Windows PC (Agent)

```bash
pip install -r agent/requirements.txt
cp agent/config.example.yaml agent/config.yaml
# Edit config.yaml with real keys
python agent/main.py
```

### Yandex Dialogs

1. https://dialogs.yandex.ru/developer/ → new skill
2. Webhook URL: `https://your-vps:8443/alice/webhook`
3. Test in testing tab

### Getting API Keys

- **GLM-4:** Register at https://open.bigmodel.cn/ → get API key (free tier)
- **VK Token:** Create app at https://dev.vk.com/ → user token with `video` scope
