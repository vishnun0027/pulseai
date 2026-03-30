# AI Behavior Anomaly Monitoring System

A high-performance, polyglot anomaly detection platform for real-time system behavior monitoring. Built with Rust, Go, and Python across a fully event-driven microservice architecture.

## Architecture

```
┌─────────────┐     HTTP      ┌─────────────┐    Redis Stream    ┌─────────────────┐
│  Rust Agent │ ──────────── │  Go Ingestion│ ───────────────── │  Python AI      │
│  collector  │              │  & Dedup     │                   │  IsolationForest│
└─────────────┘              └─────────────┘                   │  SHAP Explainer │
                                                               └────────┬────────┘
┌─────────────┐    Pub/Sub   ┌─────────────┐    Pub/Sub              │
│  FastAPI    │ ◄─────────── │  Redis      │ ◄───────────────────────┘
│  Dashboard  │              │  Broker     │
└─────────────┘              └──────┬──────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
              ┌──────────────┐            ┌─────────────────┐
              │  Go          │            │  Go             │
              │  Correlation │            │  Alert          │
              │  Engine      │            │  Dispatcher     │
              └──────────────┘            └─────────────────┘
```

## Services

| Service | Language | Role | Port |
|---------|----------|------|------|
| `agent` | Rust | Collects CPU, memory, GPU telemetry every 5s | — |
| `ingestion` | Go | Receives agent HTTP POSTs, deduplicates, publishes to Redis | 8080 |
| `ai-consumer` | Python | Consumes Redis stream, runs IsolationForest + SHAP | — |
| `correlation` | Go | Detects cluster attacks (multiple agents anomalous simultaneously) | — |
| `alerter` | Go | Dispatches Slack/webhook alerts for anomalies & cluster events | — |
| `dashboard` | Python/FastAPI | Streams live intelligence to the browser via SSE | 8000 |
| `redis` | Redis 7 | Ultra-fast pub/sub message broker | 6379 |

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd projectsys

# 2. Copy environment config (optional: set ALERT_WEBHOOK_URL for Slack alerts)
cp .env.example .env

# 3. Launch the full stack
docker compose up --build

# 4. Open the dashboard
open http://localhost:8000
```

All 7 services boot in dependency order. Redis readiness is health-checked before downstream services start.

## AI / ML Pipeline

### Anomaly Detection — `ai/`

| File | Purpose |
|------|---------|
| `features.py` | Rolling window feature engineering (mean, std over 5-sample window) |
| `model.py` | Online `IsolationForest` with incremental buffer training |
| `trainer.py` | Offline batch trainer — load from `.jsonl`, evaluate, serialize to disk |
| `drift_detector.py` | Multi-feature ADWIN drift detector — one detector per feature channel |
| `explainer.py` | SHAP `TreeExplainer` — decomposes anomaly score into feature contributions |
| `consumer.py` | Redis Stream worker — orchestrates the full inference pipeline |
| `inference.py` | End-to-end simulation: train → normal → spike → drift phases |

### Baseline Management — `baseline/`

| File | Purpose |
|------|---------|
| `drift_classifier.py` | Raw CPU/memory ADWIN drift detector |
| `baseline_manager.py` | Per-agent z-score behavioral profiling with 100-sample rolling window |

### Offline Training

```bash
# Train on a historical telemetry dump (one JSON payload per line)
uv run python -m ai.trainer path/to/telemetry.jsonl
# Model saved to models/isolation_forest.pkl
```

## Go Services

### Ingestion — `ingestion/`
- `schemas.go` — Telemetry struct mirroring the Rust agent's JSON payload
- `dedup.go` — In-memory mutex-protected idempotency cache
- `routes.go` — POST `/v1/telemetry` → validates → deduplicates → `XADD` to Redis stream
- `main.go` — Server bootstrap, reads `REDIS_HOST`/`REDIS_PORT`/`PORT` from env

### Correlation — `correlation/`
Maintains a sliding time window (default 30s) of agent anomaly events. When ≥2 agents are anomalous simultaneously, emits a `CLUSTER ALERT` to `cluster_alerts` Pub/Sub channel.

### Alerts — `alerts/`
Subscribes to both `anomalies_feed` and `cluster_alerts`. Dispatches formatted messages to configurable Slack/Teams webhook (`ALERT_WEBHOOK_URL` env var).

## Rust Agent — `agent/`

| File | Purpose |
|------|---------|
| `collector.rs` | Collects CPU, memory, per-core stats via `sysinfo`; GPU via `nvidia-smi` |
| `environment.rs` | Detects execution environment: WSL, Docker, bare-metal host |
| `state_manager.rs` | Persists session state to disk (`.agent_state.json`) |
| `gap_detector.rs` | Identifies gaps in telemetry stream (crash recovery, sleep) |
| `main.rs` | Async event loop using `tokio`; reads `TELEMETRY_URL` from env |

## Configuration

All service parameters are centralized in [`config/settings.toml`](config/settings.toml):

```toml
[redis]
host = "redis"
port = 6379

[ml]
isolation_forest_contamination = 0.1
feature_window_size = 5
baseline_min_samples = 20

[alerts]
webhook_url = ""          # Set via ALERT_WEBHOOK_URL env var
severity_threshold = 0.1  # Minimum score before alerting

[correlation]
cluster_window_s = 30     # Time window for multi-agent grouping
cluster_min_agents = 2    # Minimum agents to trigger cluster alert
```

## Local Development (without Docker)

```bash
# Python (dashboard + AI):
uv run uvicorn dashboard.main:app --port 8000
uv run python ai/consumer.py

# Go (ingestion):
cd ingestion && go run .

# Rust (agent):
cd agent && cargo run

# Redis:
docker run -d -p 6379:6379 redis
```

## Dashboard

The web UI at `http://localhost:8000` visualizes:
- **Live CPU & Memory** charts per agent (Chart.js)
- **Anomaly Risk Score** — color coded: green (normal) / red (anomalous)
- **Intelligence Event Log** — real-time stream of scored events
- **Pulse Indicator** — glows red on anomaly, green on normal baseline

Powered by **FastAPI + Server-Sent Events (SSE)** — no WebSocket, no polling.

## Alerting

Set `ALERT_WEBHOOK_URL` in `.env` to receive push notifications:
- **Single anomaly**: fires when `anomaly_score > 0.1`
- **Cluster attack**: fires when ≥2 agents anomalous within 30s window

Compatible with any webhook endpoint (Slack, Teams, Discord, PagerDuty).

## Project Structure

```
projectsys/
├── agent/                  # Rust telemetry collector
├── ingestion/              # Go HTTP ingest + Redis publisher
├── correlation/            # Go cluster attack detector
├── alerts/                 # Go webhook dispatcher
├── ai/                     # Python ML pipeline
│   ├── features.py         # Feature engineering
│   ├── model.py            # IsolationForest
│   ├── trainer.py          # Offline training
│   ├── drift_detector.py   # Multi-feature ADWIN
│   ├── explainer.py        # SHAP explainability
│   └── consumer.py         # Redis stream worker
├── baseline/               # Behavioral baseline mgmt
├── dashboard/              # FastAPI + SSE web UI
├── config/                 # Centralized settings.toml
├── docker-compose.yml      # Full stack orchestration
├── Dockerfile.ai           # Python AI worker image
└── Dockerfile.dashboard    # Dashboard image
```
