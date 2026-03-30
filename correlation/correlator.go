package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// ClusterEvent represents a multi-agent anomaly cluster
type ClusterEvent struct {
	Agents     []string  `json:"agents"`
	Count      int       `json:"count"`
	WindowStart int64    `json:"window_start"`
	WindowEnd  int64     `json:"window_end"`
}

type AnomalyEntry struct {
	AgentID   string
	Timestamp int64
	Score     float64
}

type CorrelationEngine struct {
	mu          sync.Mutex
	recentAnomalies []AnomalyEntry
	windowSecs  int64
	minAgents   int
}

func NewCorrelationEngine(windowSecs int64, minAgents int) *CorrelationEngine {
	return &CorrelationEngine{
		windowSecs: windowSecs,
		minAgents:  minAgents,
	}
}

func (c *CorrelationEngine) Observe(entry AnomalyEntry) *ClusterEvent {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now().Unix()
	cutoff := now - c.windowSecs

	// Evict old entries
	var fresh []AnomalyEntry
	for _, e := range c.recentAnomalies {
		if e.Timestamp >= cutoff {
			fresh = append(fresh, e)
		}
	}
	fresh = append(fresh, entry)
	c.recentAnomalies = fresh

	// Count unique agents in the window
	seen := make(map[string]bool)
	for _, e := range c.recentAnomalies {
		seen[e.AgentID] = true
	}

	if len(seen) >= c.minAgents {
		agents := make([]string, 0, len(seen))
		for a := range seen {
			agents = append(agents, a)
		}
		return &ClusterEvent{
			Agents:      agents,
			Count:       len(seen),
			WindowStart: cutoff,
			WindowEnd:   now,
		}
	}
	return nil
}

func RunCorrelationListener(rdb *redis.Client, engine *CorrelationEngine) {
	ctx := context.Background()
	pubsub := rdb.Subscribe(ctx, "anomalies_feed")
	defer pubsub.Close()

	fmt.Println("[Correlation] Listening on anomalies_feed channel...")

	ch := pubsub.Channel()
	for msg := range ch {
		var data map[string]interface{}
		if err := json.Unmarshal([]byte(msg.Payload), &data); err != nil {
			continue
		}

		isAnomaly, _ := data["is_anomaly"].(bool)
		if !isAnomaly {
			continue
		}

		agentID, _ := data["agent_id"].(string)
		score, _ := data["anomaly_score"].(float64)
		ts, _ := data["timestamp"].(float64)

		cluster := engine.Observe(AnomalyEntry{
			AgentID:   agentID,
			Timestamp: int64(ts),
			Score:     score,
		})

		if cluster != nil {
			b, _ := json.Marshal(cluster)
			log.Printf("[CLUSTER ALERT] %s\n", string(b))
			rdb.Publish(ctx, "cluster_alerts", string(b))
		}
	}
}
