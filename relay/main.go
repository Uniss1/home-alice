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
