package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/redis/go-redis/v9"
)

func getEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return fallback
}

func main() {
	fmt.Println("Starting AI Behavior Anomaly Go Ingestion Service...")

	redisAddr := getEnv("REDIS_HOST", "localhost") + ":" + getEnv("REDIS_PORT", "6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})

	if err := rdb.Ping(context.Background()).Err(); err != nil {
		log.Fatalf("Redis connection failed: %v", err)
	}
	fmt.Printf("Connected to Redis broker at %s\n", redisAddr)

	dedup := NewDedupCache()
	router := BuildRouter(dedup, rdb)
	RegisterMetricsHandler(router)

	port := ":" + getEnv("PORT", "8080")
	fmt.Printf("Listening on port %s\n", port)

	if err := http.ListenAndServe(port, router); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
