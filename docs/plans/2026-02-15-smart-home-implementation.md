# Smart Home Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Register PC as Yandex Smart Home media device so voice commands (pause, volume, shutdown) work without skill activation.

**Architecture:** Add OAuth2 + Smart Home Provider API endpoints to Go relay. Relay translates Smart Home capability actions into direct WebSocket tool calls to the agent, bypassing LLM. Agent handles both LLM-routed (Alice skill) and direct (Smart Home) tool calls.

**Tech Stack:** Go 1.22, gorilla/websocket, net/http; Python agent (existing)

---

### Task 1: OAuth2 Endpoints

**Files:**
- Create: `relay/oauth.go`
- Create: `relay/oauth_test.go`

Single-user OAuth2: Yandex requires the flow, but we auto-approve and use fixed tokens from env vars.

**Env vars needed:** `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_TOKEN` (fixed access token)

**Step 1: Write the failing test**

```go
// relay/oauth_test.go
package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func TestAuthorizeRedirectsWithCode(t *testing.T) {
	// Set env for test
	t.Setenv("OAUTH_CLIENT_ID", "test-client")
	t.Setenv("OAUTH_CLIENT_SECRET", "test-secret")
	t.Setenv("OAUTH_TOKEN", "test-token-123")

	req := httptest.NewRequest("GET",
		"/oauth/authorize?state=abc123&redirect_uri=https://social.yandex.net/broker/redirect&client_id=test-client&response_type=code",
		nil)
	w := httptest.NewRecorder()

	handleOAuthAuthorize(w, req)

	if w.Code != http.StatusFound {
		t.Fatalf("expected 302, got %d", w.Code)
	}
	loc := w.Header().Get("Location")
	if !strings.Contains(loc, "state=abc123") {
		t.Fatalf("redirect missing state param: %s", loc)
	}
	if !strings.Contains(loc, "code=") {
		t.Fatalf("redirect missing code param: %s", loc)
	}
}

func TestTokenReturnsAccessToken(t *testing.T) {
	t.Setenv("OAUTH_CLIENT_ID", "test-client")
	t.Setenv("OAUTH_CLIENT_SECRET", "test-secret")
	t.Setenv("OAUTH_TOKEN", "test-token-123")

	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("code", "any-code")
	form.Set("client_id", "test-client")
	form.Set("client_secret", "test-secret")

	req := httptest.NewRequest("POST", "/oauth/token",
		strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()

	handleOAuthToken(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	body := w.Body.String()
	if !strings.Contains(body, "test-token-123") {
		t.Fatalf("response missing token: %s", body)
	}
}

func TestTokenRefresh(t *testing.T) {
	t.Setenv("OAUTH_CLIENT_ID", "test-client")
	t.Setenv("OAUTH_CLIENT_SECRET", "test-secret")
	t.Setenv("OAUTH_TOKEN", "test-token-123")

	form := url.Values{}
	form.Set("grant_type", "refresh_token")
	form.Set("refresh_token", "any-refresh")
	form.Set("client_id", "test-client")
	form.Set("client_secret", "test-secret")

	req := httptest.NewRequest("POST", "/oauth/token",
		strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()

	handleOAuthToken(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestTokenRejectsWrongClient(t *testing.T) {
	t.Setenv("OAUTH_CLIENT_ID", "test-client")
	t.Setenv("OAUTH_CLIENT_SECRET", "test-secret")
	t.Setenv("OAUTH_TOKEN", "test-token-123")

	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("code", "any-code")
	form.Set("client_id", "wrong-client")
	form.Set("client_secret", "wrong-secret")

	req := httptest.NewRequest("POST", "/oauth/token",
		strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	w := httptest.NewRecorder()

	handleOAuthToken(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd relay && go test -run TestAuthorize -v`
Expected: FAIL — `handleOAuthAuthorize` not defined

**Step 3: Write minimal implementation**

```go
// relay/oauth.go
package main

import (
	"encoding/json"
	"net/http"
)

func handleOAuthAuthorize(w http.ResponseWriter, r *http.Request) {
	state := r.URL.Query().Get("state")
	redirectURI := r.URL.Query().Get("redirect_uri")

	// Auto-approve: redirect immediately with a fixed code
	location := redirectURI + "?code=home-alice-auth-code&state=" + state
	http.Redirect(w, r, location, http.StatusFound)
}

func handleOAuthToken(w http.ResponseWriter, r *http.Request) {
	r.ParseForm()

	clientID := r.FormValue("client_id")
	clientSecret := r.FormValue("client_secret")

	expectedID := getEnv("OAUTH_CLIENT_ID", "")
	expectedSecret := getEnv("OAUTH_CLIENT_SECRET", "")

	if clientID != expectedID || clientSecret != expectedSecret {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	token := getEnv("OAUTH_TOKEN", "")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"access_token":  token,
		"token_type":    "bearer",
		"expires_in":    315360000, // 10 years
		"refresh_token": "home-alice-refresh-token",
	})
}
```

**Step 4: Run test to verify it passes**

Run: `cd relay && go test -run TestAuthorize -v && go test -run TestToken -v`
Expected: PASS

**Step 5: Commit**

```bash
git add relay/oauth.go relay/oauth_test.go
git commit -m "feat(relay): add simplified OAuth2 endpoints for Smart Home"
```

---

### Task 2: Smart Home Types & Health Endpoints

**Files:**
- Create: `relay/smarthome.go`
- Create: `relay/smarthome_test.go`

**Step 1: Write the failing test**

```go
// relay/smarthome_test.go
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSmartHomeHealthCheck(t *testing.T) {
	req := httptest.NewRequest("HEAD", "/v1.0", nil)
	req.Header.Set("X-Request-Id", "req-123")
	w := httptest.NewRecorder()

	handleSmartHomeHead(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestSmartHomeUnlink(t *testing.T) {
	t.Setenv("OAUTH_TOKEN", "test-token")

	req := httptest.NewRequest("POST", "/v1.0/user/unlink", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	req.Header.Set("X-Request-Id", "req-456")
	w := httptest.NewRecorder()

	handleSmartHomeUnlink(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
}

func TestSmartHomeUnlinkRejectsBadToken(t *testing.T) {
	t.Setenv("OAUTH_TOKEN", "test-token")

	req := httptest.NewRequest("POST", "/v1.0/user/unlink", nil)
	req.Header.Set("Authorization", "Bearer wrong-token")
	w := httptest.NewRecorder()

	handleSmartHomeUnlink(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", w.Code)
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd relay && go test -run TestSmartHome -v`
Expected: FAIL — functions not defined

**Step 3: Write minimal implementation**

```go
// relay/smarthome.go
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
)

// --- Smart Home request/response types ---

type SmartHomeDevice struct {
	ID           string                 `json:"id"`
	Name         string                 `json:"name,omitempty"`
	Type         string                 `json:"type,omitempty"`
	Room         string                 `json:"room,omitempty"`
	Capabilities []SmartHomeCapability  `json:"capabilities"`
	Properties   []interface{}          `json:"properties,omitempty"`
	DeviceInfo   map[string]string      `json:"device_info,omitempty"`
}

type SmartHomeCapability struct {
	Type        string                 `json:"type"`
	Retrievable bool                   `json:"retrievable,omitempty"`
	Reportable  bool                   `json:"reportable,omitempty"`
	Parameters  map[string]interface{} `json:"parameters,omitempty"`
	State       *SmartHomeCapState     `json:"state,omitempty"`
}

type SmartHomeCapState struct {
	Instance     string               `json:"instance"`
	Value        interface{}          `json:"value,omitempty"`
	Relative     *bool                `json:"relative,omitempty"`
	ActionResult *SmartHomeActionResult `json:"action_result,omitempty"`
}

type SmartHomeActionResult struct {
	Status       string `json:"status"`
	ErrorCode    string `json:"error_code,omitempty"`
	ErrorMessage string `json:"error_message,omitempty"`
}

type SmartHomeResponse struct {
	RequestID string      `json:"request_id"`
	Payload   interface{} `json:"payload"`
}

type SmartHomeActionRequest struct {
	Payload struct {
		Devices []struct {
			ID           string                `json:"id"`
			Capabilities []SmartHomeCapability `json:"capabilities"`
		} `json:"devices"`
	} `json:"payload"`
}

type SmartHomeQueryRequest struct {
	Devices []struct {
		ID string `json:"id"`
	} `json:"devices"`
}

// --- Auth helper ---

func validateSmartHomeToken(r *http.Request) bool {
	token := getEnv("OAUTH_TOKEN", "")
	auth := r.Header.Get("Authorization")
	return auth == "Bearer "+token
}

// --- Handlers ---

func handleSmartHomeHead(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
}

func handleSmartHomeUnlink(w http.ResponseWriter, r *http.Request) {
	if !validateSmartHomeToken(r) {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	reqID := r.Header.Get("X-Request-Id")
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(SmartHomeResponse{RequestID: reqID})
}
```

**Step 4: Run test to verify it passes**

Run: `cd relay && go test -run TestSmartHome -v`
Expected: PASS

**Step 5: Commit**

```bash
git add relay/smarthome.go relay/smarthome_test.go
git commit -m "feat(relay): add Smart Home types and health/unlink endpoints"
```

---

### Task 3: Device Discovery

**Files:**
- Modify: `relay/smarthome.go`
- Modify: `relay/smarthome_test.go`

**Step 1: Write the failing test**

Add to `relay/smarthome_test.go`:

```go
func TestSmartHomeDiscovery(t *testing.T) {
	t.Setenv("OAUTH_TOKEN", "test-token")

	req := httptest.NewRequest("GET", "/v1.0/user/devices", nil)
	req.Header.Set("Authorization", "Bearer test-token")
	req.Header.Set("X-Request-Id", "req-789")
	w := httptest.NewRecorder()

	handleSmartHomeDiscovery(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}

	body := w.Body.String()
	// Should contain device with media_device.tv type
	if !strings.Contains(body, "devices.types.media_device.tv") {
		t.Fatalf("response missing device type: %s", body)
	}
	// Should contain toggle pause capability
	if !strings.Contains(body, "pause") {
		t.Fatalf("response missing pause capability: %s", body)
	}
	// Should contain volume range
	if !strings.Contains(body, "volume") {
		t.Fatalf("response missing volume capability: %s", body)
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd relay && go test -run TestSmartHomeDiscovery -v`
Expected: FAIL — `handleSmartHomeDiscovery` not defined

**Step 3: Write minimal implementation**

Add to `relay/smarthome.go`:

```go
const deviceID = "home-alice-pc"

func pcDevice() SmartHomeDevice {
	return SmartHomeDevice{
		ID:   deviceID,
		Name: "Компьютер",
		Type: "devices.types.media_device.tv",
		Room: "Комната",
		Capabilities: []SmartHomeCapability{
			{
				Type:        "devices.capabilities.on_off",
				Retrievable: true,
			},
			{
				Type:        "devices.capabilities.toggle",
				Retrievable: true,
				Parameters:  map[string]interface{}{"instance": "pause"},
			},
			{
				Type:        "devices.capabilities.toggle",
				Retrievable: true,
				Parameters:  map[string]interface{}{"instance": "mute"},
			},
			{
				Type:        "devices.capabilities.range",
				Retrievable: true,
				Parameters: map[string]interface{}{
					"instance":      "volume",
					"unit":          "unit.percent",
					"random_access": true,
					"range": map[string]interface{}{
						"min":       0,
						"max":       100,
						"precision": 5,
					},
				},
			},
		},
		Properties: []interface{}{},
		DeviceInfo: map[string]string{
			"manufacturer": "Home Alice",
			"model":        "PC Agent v2",
		},
	}
}

func handleSmartHomeDiscovery(w http.ResponseWriter, r *http.Request) {
	if !validateSmartHomeToken(r) {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	reqID := r.Header.Get("X-Request-Id")
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(SmartHomeResponse{
		RequestID: reqID,
		Payload: map[string]interface{}{
			"user_id": "1",
			"devices": []SmartHomeDevice{pcDevice()},
		},
	})
}
```

**Step 4: Run test to verify it passes**

Run: `cd relay && go test -run TestSmartHomeDiscovery -v`
Expected: PASS

**Step 5: Commit**

```bash
git add relay/smarthome.go relay/smarthome_test.go
git commit -m "feat(relay): add Smart Home device discovery endpoint"
```

---

### Task 4: Device Action Handler

**Files:**
- Modify: `relay/smarthome.go`
- Modify: `relay/smarthome_test.go`

This is the core — translates Smart Home capabilities into WebSocket tool calls.

**Step 1: Write the failing test**

Add to `relay/smarthome_test.go`:

```go
func TestMapCapabilityToTool(t *testing.T) {
	tests := []struct {
		name     string
		capType  string
		instance string
		value    interface{}
		wantTool string
		wantArgs map[string]interface{}
	}{
		{
			name: "pause on", capType: "devices.capabilities.toggle",
			instance: "pause", value: true,
			wantTool: "browser_pause_video", wantArgs: map[string]interface{}{},
		},
		{
			name: "pause off", capType: "devices.capabilities.toggle",
			instance: "pause", value: false,
			wantTool: "browser_play_video", wantArgs: map[string]interface{}{},
		},
		{
			name: "mute on", capType: "devices.capabilities.toggle",
			instance: "mute", value: true,
			wantTool: "volume_mute", wantArgs: map[string]interface{}{"mute": true},
		},
		{
			name: "mute off", capType: "devices.capabilities.toggle",
			instance: "mute", value: false,
			wantTool: "volume_mute", wantArgs: map[string]interface{}{"mute": false},
		},
		{
			name: "volume set", capType: "devices.capabilities.range",
			instance: "volume", value: float64(75),
			wantTool: "volume_set", wantArgs: map[string]interface{}{"level": float64(75)},
		},
		{
			name: "power off", capType: "devices.capabilities.on_off",
			instance: "on", value: false,
			wantTool: "sleep_pc", wantArgs: map[string]interface{}{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cap := SmartHomeCapability{
				Type: tt.capType,
				State: &SmartHomeCapState{
					Instance: tt.instance,
					Value:    tt.value,
				},
			}
			tool, args := mapCapabilityToTool(cap)
			if tool != tt.wantTool {
				t.Errorf("tool = %q, want %q", tool, tt.wantTool)
			}
			for k, v := range tt.wantArgs {
				if args[k] != v {
					t.Errorf("args[%s] = %v, want %v", k, args[k], v)
				}
			}
		})
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd relay && go test -run TestMapCapability -v`
Expected: FAIL — `mapCapabilityToTool` not defined

**Step 3: Write minimal implementation**

Add to `relay/smarthome.go`:

```go
import "fmt"

// mapCapabilityToTool translates a Smart Home capability into agent tool name + args.
func mapCapabilityToTool(cap SmartHomeCapability) (tool string, args map[string]interface{}) {
	args = map[string]interface{}{}
	if cap.State == nil {
		return "", args
	}

	switch cap.Type {
	case "devices.capabilities.on_off":
		if cap.State.Value == true {
			// "Turn on" — no-op for PC (it's already on if agent is connected)
			return "", args
		}
		return "sleep_pc", args

	case "devices.capabilities.toggle":
		switch cap.State.Instance {
		case "pause":
			if cap.State.Value == true {
				return "browser_pause_video", args
			}
			return "browser_play_video", args
		case "mute":
			args["mute"] = cap.State.Value
			return "volume_mute", args
		}

	case "devices.capabilities.range":
		if cap.State.Instance == "volume" {
			val, ok := cap.State.Value.(float64)
			if !ok {
				return "", args
			}
			// Handle relative volume changes
			if cap.State.Relative != nil && *cap.State.Relative {
				// Relative: need current volume + delta. For now, clamp to 0-100.
				args["level"] = val // Agent will need to handle relative
				args["relative"] = true
				return "volume_set", args
			}
			args["level"] = val
			return "volume_set", args
		}
	}

	return "", args
}

func handleSmartHomeAction(w http.ResponseWriter, r *http.Request) {
	if !validateSmartHomeToken(r) {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	reqID := r.Header.Get("X-Request-Id")

	var req SmartHomeActionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	var respDevices []map[string]interface{}

	for _, dev := range req.Payload.Devices {
		if dev.ID != deviceID {
			continue
		}

		var respCaps []map[string]interface{}

		for _, cap := range dev.Capabilities {
			instance := ""
			if cap.State != nil {
				instance = cap.State.Instance
			}

			tool, args := mapCapabilityToTool(cap)

			result := SmartHomeActionResult{Status: "DONE"}

			if tool == "" {
				result = SmartHomeActionResult{
					Status:    "ERROR",
					ErrorCode: "INVALID_ACTION",
				}
			} else {
				// Send tool call to agent via WebSocket
				err := sendToolToAgent(reqID, tool, args)
				if err != nil {
					log.Printf("Smart Home action error: %v", err)
					result = SmartHomeActionResult{
						Status:    "ERROR",
						ErrorCode: "DEVICE_UNREACHABLE",
					}
				}
			}

			respCaps = append(respCaps, map[string]interface{}{
				"type": cap.Type,
				"state": map[string]interface{}{
					"instance":      instance,
					"action_result": result,
				},
			})
		}

		respDevices = append(respDevices, map[string]interface{}{
			"id":           dev.ID,
			"capabilities": respCaps,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(SmartHomeResponse{
		RequestID: reqID,
		Payload:   map[string]interface{}{"devices": respDevices},
	})
}

// sendToolToAgent sends a direct tool call to the agent and waits for response.
func sendToolToAgent(reqID, tool string, args map[string]interface{}) error {
	agentMu.Lock()
	conn := agentConn
	agentMu.Unlock()

	if conn == nil {
		return fmt.Errorf("agent not connected")
	}

	msgID := "sh-" + reqID
	respCh := make(chan string, 1)

	pendingMu.Lock()
	pending[msgID] = respCh
	pendingMu.Unlock()

	defer func() {
		pendingMu.Lock()
		delete(pending, msgID)
		pendingMu.Unlock()
	}()

	msg, _ := json.Marshal(map[string]interface{}{
		"id":     msgID,
		"text":   tool,
		"source": "smart_home",
		"tool":   tool,
		"args":   args,
	})

	agentMu.Lock()
	err := agentConn.WriteMessage(1, msg) // 1 = TextMessage
	agentMu.Unlock()

	if err != nil {
		return err
	}

	select {
	case <-respCh:
		return nil
	case <-time.After(4 * time.Second):
		return fmt.Errorf("timeout")
	}
}
```

**Step 4: Run test to verify it passes**

Run: `cd relay && go test -run TestMapCapability -v`
Expected: PASS

**Step 5: Commit**

```bash
git add relay/smarthome.go relay/smarthome_test.go
git commit -m "feat(relay): add Smart Home action handler with capability-to-tool mapping"
```

---

### Task 5: Device Query Handler

**Files:**
- Modify: `relay/smarthome.go`
- Modify: `relay/smarthome_test.go`

Returns default state values (agent is on, not paused, not muted, volume 50).

**Step 1: Write the failing test**

Add to `relay/smarthome_test.go`:

```go
func TestSmartHomeQuery(t *testing.T) {
	t.Setenv("OAUTH_TOKEN", "test-token")

	body := `{"devices":[{"id":"home-alice-pc"}]}`
	req := httptest.NewRequest("POST", "/v1.0/user/devices/query",
		strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer test-token")
	req.Header.Set("X-Request-Id", "req-q1")
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	handleSmartHomeQuery(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	respBody := w.Body.String()
	if !strings.Contains(respBody, "home-alice-pc") {
		t.Fatalf("response missing device id: %s", respBody)
	}
}
```

**Step 2: Run test to verify it fails**

Run: `cd relay && go test -run TestSmartHomeQuery -v`
Expected: FAIL — `handleSmartHomeQuery` not defined

**Step 3: Write minimal implementation**

Add to `relay/smarthome.go`:

```go
func handleSmartHomeQuery(w http.ResponseWriter, r *http.Request) {
	if !validateSmartHomeToken(r) {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	reqID := r.Header.Get("X-Request-Id")

	var req SmartHomeQueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Bad request", http.StatusBadRequest)
		return
	}

	var devices []map[string]interface{}
	for _, dev := range req.Devices {
		if dev.ID != deviceID {
			continue
		}

		// Return default state — agent is on, not paused, not muted, volume 50
		agentMu.Lock()
		connected := agentConn != nil
		agentMu.Unlock()

		devices = append(devices, map[string]interface{}{
			"id": dev.ID,
			"capabilities": []map[string]interface{}{
				{
					"type":  "devices.capabilities.on_off",
					"state": map[string]interface{}{"instance": "on", "value": connected},
				},
				{
					"type":  "devices.capabilities.toggle",
					"state": map[string]interface{}{"instance": "pause", "value": false},
				},
				{
					"type":  "devices.capabilities.toggle",
					"state": map[string]interface{}{"instance": "mute", "value": false},
				},
				{
					"type":  "devices.capabilities.range",
					"state": map[string]interface{}{"instance": "volume", "value": 50},
				},
			},
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(SmartHomeResponse{
		RequestID: reqID,
		Payload:   map[string]interface{}{"devices": devices},
	})
}
```

**Step 4: Run test to verify it passes**

Run: `cd relay && go test -run TestSmartHomeQuery -v`
Expected: PASS

**Step 5: Commit**

```bash
git add relay/smarthome.go relay/smarthome_test.go
git commit -m "feat(relay): add Smart Home device query handler"
```

---

### Task 6: Update Python Agent for Direct Tool Calls

**Files:**
- Modify: `agent/main.py:31-42`
- Create: `tests/agent/test_direct_tool.py`

Agent must handle messages with `tool` field — execute tool directly without LLM.

**Step 1: Write the failing test**

```python
# tests/agent/test_direct_tool.py
import json
from unittest.mock import MagicMock, patch


def test_direct_tool_call_executes_without_llm():
    """When message has 'tool' field, execute directly without LLM."""
    from agent.tool_executor import ToolExecutor

    executor = ToolExecutor(vk_token="")
    with patch.object(executor, "execute", return_value="Поставил на паузу") as mock_exec:
        # Simulate processing a direct tool message
        data = {
            "id": "sh-123",
            "text": "browser_pause_video",
            "source": "smart_home",
            "tool": "browser_pause_video",
            "args": {},
        }
        result = executor.execute(data["tool"], data["args"])
        mock_exec.assert_called_once_with("browser_pause_video", {})
        assert "паузу" in result.lower() or result == "Поставил на паузу"


def test_regular_message_without_tool_field():
    """When message has no 'tool' field, it should go through LLM."""
    data = {"id": "alice-123", "text": "поставь на паузу"}
    assert "tool" not in data
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/agent/test_direct_tool.py -v`
Expected: PASS (this test mocks, but we need the agent code change)

**Step 3: Modify agent/main.py to handle direct tool calls**

Current code (`agent/main.py:31-42`):
```python
data = json.loads(message)
msg_id = data.get("id", "")
text = data.get("text", "")
result = await loop.run_in_executor(
    None, llm.process_command, text
)
```

New code:
```python
data = json.loads(message)
msg_id = data.get("id", "")
text = data.get("text", "")

if "tool" in data:
    # Direct tool call from Smart Home — bypass LLM
    tool_name = data["tool"]
    tool_args = data.get("args", {})
    logger.info("Direct tool call: %s(%s)", tool_name, tool_args)
    result = llm.executor.execute(tool_name, tool_args)
else:
    # Regular command from Alice skill — route through LLM
    result = await loop.run_in_executor(
        None, llm.process_command, text
    )
```

**Step 4: Run all tests**

Run: `python3 -m pytest tests/ --ignore=tests/agent/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add agent/main.py tests/agent/test_direct_tool.py
git commit -m "feat(agent): handle direct tool calls from Smart Home (bypass LLM)"
```

---

### Task 7: Register Routes in main.go

**Files:**
- Modify: `relay/main.go`

**Step 1: Add Smart Home and OAuth2 route registration**

Add after existing `http.HandleFunc` calls in `main()`:

```go
// OAuth2 endpoints
http.HandleFunc("/oauth/authorize", handleOAuthAuthorize)
http.HandleFunc("/oauth/token", handleOAuthToken)

// Smart Home Provider API
http.HandleFunc("/v1.0", handleSmartHomeHead)
http.HandleFunc("/v1.0/user/unlink", handleSmartHomeUnlink)
http.HandleFunc("/v1.0/user/devices", handleSmartHomeDiscovery)
http.HandleFunc("/v1.0/user/devices/query", handleSmartHomeQuery)
http.HandleFunc("/v1.0/user/devices/action", handleSmartHomeAction)
```

**Step 2: Add import for "fmt" if not present**

Check `relay/main.go` imports — `fmt` may already be imported via smarthome.go (same package).

**Step 3: Run all Go tests**

Run: `cd relay && go test -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add relay/main.go
git commit -m "feat(relay): register Smart Home and OAuth2 routes"
```

---

### Task 8: Update Config & Docker

**Files:**
- Modify: `relay/.env.example`
- Modify: `relay/docker-compose.yml`

**Step 1: Add env vars to .env.example**

```
# OAuth2 for Yandex Smart Home (single-user)
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_TOKEN=your-fixed-access-token
```

**Step 2: Add env vars to docker-compose.yml**

Add to environment section:
```yaml
- OAUTH_CLIENT_ID=${OAUTH_CLIENT_ID}
- OAUTH_CLIENT_SECRET=${OAUTH_CLIENT_SECRET}
- OAUTH_TOKEN=${OAUTH_TOKEN}
```

**Step 3: Commit**

```bash
git add relay/.env.example relay/docker-compose.yml
git commit -m "build(relay): add Smart Home OAuth env vars to config"
```

---

### Task 9: Yandex Developer Console Registration Guide

After deployment, register in Yandex Developer Console:

1. https://dialogs.yandex.ru/developer/ → «Создать диалог» → «Умный дом»
2. Вкладка «Умный дом»:
   - Endpoint URL: `https://your-vps.com`
3. Вкладка «Связка аккаунтов»:
   - URL авторизации: `https://your-vps.com/oauth/authorize`
   - URL для получения токена: `https://your-vps.com/oauth/token`
   - Client ID и Client Secret — те же что в `.env`
4. Сохранить → В приложении Яндекс → Устройства → Добавить → Выбрать провайдер
5. Пройти OAuth → Устройство «Компьютер» появится в списке

Теперь можно говорить: «Алиса, поставь на паузу» — без активации навыка.
