package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/redis/go-redis/v9"
)

func BuildRouter(dedup *DedupCache, rdb *redis.Client) *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("/v1/telemetry", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var payload AgentPayload
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			http.Error(w, "Bad request", http.StatusBadRequest)
			return
		}

		if dedup.IsDuplicate(payload.AgentID, payload.Timestamp) {
			w.WriteHeader(http.StatusOK)
			return
		}

		// Push to true Redis stream bridging Go to Python
		ctx := context.Background()
		payloadBytes, _ := json.Marshal(payload)
		
		err := rdb.XAdd(ctx, &redis.XAddArgs{
			Stream: "telemetry_stream",
			Values: map[string]interface{}{"payload": string(payloadBytes)},
		}).Err()

		if err != nil {
			fmt.Printf("Redis Stream Error: %v\n", err)
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}

		fmt.Printf("[Redis Push] Agent: %s | CPU: %.2f | Time: %d\n", payload.AgentID, payload.Metrics.CpuUsage, payload.Timestamp)

		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok"}`))
	})

	return mux
}
