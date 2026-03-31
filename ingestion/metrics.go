package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// ── Metric declarations ────────────────────────────────────────────────────

var (
	// Total telemetry payloads received (all)
	telemetryReceived = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "ingestion_telemetry_received_total",
		Help: "Total number of telemetry payloads received by the ingestion service.",
	})

	// Payloads accepted (passed dedup and pushed to Redis)
	telemetryAccepted = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "ingestion_telemetry_accepted_total",
		Help: "Total payloads accepted (not deduplicated) and forwarded to Redis.",
	})

	// Payloads dropped as duplicates
	telemetryDuplicated = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "ingestion_telemetry_duplicated_total",
		Help: "Total payloads dropped by the deduplication cache.",
	})

	// Redis push errors
	redisErrors = prometheus.NewCounter(prometheus.CounterOpts{
		Name: "ingestion_redis_errors_total",
		Help: "Total errors encountered when publishing to Redis Stream.",
	})

	// Current dedup cache size (gauge)
	dedupCacheSize = prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "ingestion_dedup_cache_size",
		Help: "Current number of entries in the in-memory dedup cache.",
	})
)

func init() {
	prometheus.MustRegister(
		telemetryReceived,
		telemetryAccepted,
		telemetryDuplicated,
		redisErrors,
		dedupCacheSize,
	)
}

// RegisterMetricsHandler adds /metrics to the given ServeMux.
func RegisterMetricsHandler(mux *http.ServeMux) {
	mux.Handle("/metrics", promhttp.Handler())
}
