package main

import (
	"context"
	"fmt"
	"os"
	"github.com/redis/go-redis/v9"
)

func main() {
	redisAddr := getEnv("REDIS_HOST", "localhost") + ":" + getEnv("REDIS_PORT", "6379")
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		panic(fmt.Sprintf("Redis connection failed: %v", err))
	}
	fmt.Printf("Starting Correlation Engine, connected to %s\n", redisAddr)
	engine := NewCorrelationEngine(30, 2)
	RunCorrelationListener(rdb, engine)
}

func getEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok { return v }
	return fallback
}
