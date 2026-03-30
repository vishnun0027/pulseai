# Ingestion Service (Go)

## Overview
The `ingestion/` module constitutes an ultra-low latency, stateless API written in Go. It operates horizontally scaling behind Envoy/NGINX.

## Responsibilities
- **Endpoint Exposer**: Receives telemetry streams (gRPC/Protobuf) directly from `agent/` nodes.
- **Validation & Dedup**: Implements idempotent guarantees to ensure duplicate telemetry packets from agents are discarded.
- **Data Forwarding**: Safely marshals and queues the validated metrics down into the central message broker (Redis Streams, NATS, or Kafka depending on enterprise scale).
