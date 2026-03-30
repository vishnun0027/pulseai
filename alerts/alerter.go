package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/redis/go-redis/v9"
)

type AlertPayload struct {
	Text string `json:"text"`
}

func sendWebhookAlert(webhookURL string, message string) {
	if webhookURL == "" {
		fmt.Printf("[Alert] Webhook not configured. Message: %s\n", message)
		return
	}
	body, _ := json.Marshal(AlertPayload{Text: message})
	resp, err := http.Post(webhookURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("[Alert] Failed to send webhook: %v\n", err)
		return
	}
	defer resp.Body.Close()
	fmt.Printf("[Alert] Webhook sent: %s\n", message)
}

func RunAlertListener(rdb *redis.Client) {
	ctx := context.Background()
	webhookURL := os.Getenv("ALERT_WEBHOOK_URL") // Override via env var

	// Subscribe to both single anomalies and cluster events
	pubsub := rdb.Subscribe(ctx, "anomalies_feed", "cluster_alerts")
	defer pubsub.Close()

	fmt.Println("[Alerts] Listening for anomalies and cluster events...")

	ch := pubsub.Channel()
	for msg := range ch {
		var data map[string]interface{}
		if err := json.Unmarshal([]byte(msg.Payload), &data); err != nil {
			continue
		}

		switch msg.Channel {
		case "anomalies_feed":
			isAnomaly, _ := data["is_anomaly"].(bool)
			score, _ := data["anomaly_score"].(float64)
			agentID, _ := data["agent_id"].(string)
			if isAnomaly && score > 0.1 {
				alert := fmt.Sprintf("⚠️ ANOMALY: Agent %s flagged with score %.3f", agentID, score)
				sendWebhookAlert(webhookURL, alert)
			}
		case "cluster_alerts":
			agents, _ := data["agents"].([]interface{})
			alert := fmt.Sprintf("🚨 CLUSTER ATTACK: %d agents anomalous simultaneously! %v", len(agents), agents)
			sendWebhookAlert(webhookURL, alert)
		}
	}
}
