# PulseAI

> Real-time AI-powered system behavior monitoring with anomaly detection, SHAP explainability, and a self-learning feedback loop.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?logo=python&logoColor=white)](https://python.org)
[![Go](https://img.shields.io/badge/Go-1.22-00add8?logo=go&logoColor=white)](https://go.dev)
[![Rust](https://img.shields.io/badge/Rust-stable-f74c00?logo=rust&logoColor=white)](https://rust-lang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

---

## Overview

**PulseAI** continuously observes the runtime behavior of machines (CPU, memory, load, GPU) using a lightweight Rust agent, streams telemetry through a Go ingestion pipeline, and scores each event with an unsupervised IsolationForest model running in Python. Anomalies are explained with SHAP feature attribution, persisted to TimescaleDB, and surfaced through a live web dashboard with SSE real-time updates.

Users can label anomalies directly from the UI to drive a feedback loop that adjusts the model's sensitivity over time.

---

## Features

- **Polyglot microservices** — Rust agent, Go ingestion/correlation/alerts, Python ML/dashboard
- **Unsupervised anomaly detection** — IsolationForest with online buffer training, no labels required
- **ADWIN concept drift detection** — adapts automatically when system behavior shifts
- **SHAP explainability** — every anomaly shows which features drove the score
- **Self-learning feedback loop** — False Positive / True Anomaly / Expected Change labels adjust model weights
- **TimescaleDB persistence** — full history of anomaly events and feedback labels
- **REST API + SSE** — real-time streaming and paginated historical queries
- **Prometheus + Grafana** — built-in observability for all services
- **Cluster attack detection** — Go correlation engine detects coordinated multi-agent anomalies

---

## Architecture

```
Rust Agent  ──HTTP──►  Go Ingestion  ──Stream──►  Python AI Worker
                           │                            │
                      /metrics                    IsolationForest
                       (Prom)                     ADWIN + SHAP
                                                       │
                           ◄───── Redis Pub/Sub ───────┤
                           │                           │
                    Go Correlation              TimescaleDB
                    Go Alerter                  (persistence)
                           │
                    FastAPI Dashboard
                    SSE + REST API
                    Chart.js Frontend
                           │
                    Prometheus ── Grafana
```

---

## Quick Start

**Requirements:** Docker ≥ 24, Docker Compose ≥ 2.20

```bash
# 1. Clone
git clone https://github.com/your-org/anomaly-system.git
cd anomaly-system

# 2. Configure
cp .env.example .env
# Edit .env — set ALERT_WEBHOOK_URL for Slack alerts (optional)

# 3. Launch
docker compose up --build

# 4. Open dashboard
open http://localhost:8000
```

All 10 services start automatically with health-checked dependency ordering.

---

## Dashboard

**`http://localhost:8000`**

| Panel | Description |
|---|---|
| Live Metrics | Dual-axis CPU + Memory chart, real-time per-agent |
| Event Log | Streaming feed: anomalies, drift events, stable baseline |
| SHAP Explanation | Feature importance bars for the latest anomaly |
| Feedback | Label events to improve model sensitivity |
| Historical Browser | Paginated query with agent / time / severity filters |

---

## Services & Ports

| Service | Port | Description |
|---|---|---|
| Dashboard | `8000` | Web UI + REST API |
| Ingestion API | `8080` | Telemetry receiver (`POST /v1/telemetry`) |
| AI Worker metrics | `9090` | Prometheus metrics (Python) |
| Prometheus | `9091` | Metrics aggregator UI |
| Grafana | `3000` | Visualization (default login in `.env`) |
| Redis | `6379` | Message broker (internal) |
| TimescaleDB | `5433` | Time-series database (internal) |

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/stream` | SSE live anomaly stream |
| `GET` | `/api/anomalies` | Paginated history (filters: `agent_id`, `from_ts`, `to_ts`, `only_anomalies`) |
| `GET` | `/api/anomalies/{id}` | Single event with SHAP values |
| `GET` | `/api/agents` | Per-agent stats (count, anomaly rate, last seen) |
| `POST` | `/api/feedback` | Submit a feedback label |
| `GET` | `/api/health` | Service health check |

**Feedback labels:** `false_positive` · `true_anomaly` · `expected_change`

---

## Configuration

All settings live in [`config/settings.toml`](config/settings.toml).  
Secrets and environment-specific values go in `.env` (git-ignored — see `.env.example`).

| Key setting | Default | Description |
|---|---|---|
| `ml.isolation_forest_contamination` | `0.1` | Expected anomaly fraction (0–1) |
| `ml.feature_window_size` | `5` | Rolling window for feature engineering |
| `ml.baseline_min_samples` | `20` | Samples before model trains |
| `alerts.severity_threshold` | `0.1` | Min score to trigger webhook alert |
| `correlation.cluster_window_s` | `30` | Multi-agent correlation window (seconds) |
| `correlation.cluster_min_agents` | `2` | Agents required to trigger cluster alert |

---

## Project Structure

```
.
├── agent/              # Rust — system telemetry collector (sysinfo, tokio)
├── ingestion/          # Go  — HTTP receiver, dedup, Redis Stream publisher
├── correlation/        # Go  — multi-agent cluster attack detector
├── alerts/             # Go  — Slack/Teams webhook dispatcher
├── ai/                 # Python — IsolationForest, ADWIN, SHAP, Prometheus metrics
├── baseline/           # Python — per-agent z-score behavioral profiling
├── feedback/           # Python — feedback → weight adjustment → baseline reset
├── storage/            # Python — async DB pool, Redis helpers, Pydantic models
├── dashboard/          # Python — FastAPI app, SSE stream, REST API, web UI
│   └── static/         # Chart.js frontend (HTML, CSS, JS)
├── proto/              # Protobuf definitions
├── config/
│   ├── settings.toml   # Centralized configuration
│   └── prometheus.yml  # Prometheus scrape targets
├── docs/               # Technical documentation
├── .env.example        # Environment variable template (copy to .env)
├── docker-compose.yml  # Full 10-service orchestration
├── Dockerfile.ai       # Python AI worker image
└── Dockerfile.dashboard # Dashboard image
```

---

## Observability

### Prometheus Metrics

The system exposes two metrics endpoints scraped by Prometheus:

- **Go ingestion** — `http://localhost:8080/metrics`  
  `ingestion_telemetry_received_total`, `ingestion_telemetry_accepted_total`, `ingestion_telemetry_duplicated_total`

- **Python AI worker** — `http://localhost:9090/metrics`  
  `ai_inference_processed_total`, `ai_anomalies_detected_total`, `ai_drift_detected_total`, `ai_anomaly_score` (histogram)

### Grafana

Open `http://localhost:3000`, add a Prometheus data source at `http://prometheus:9090`, and start building dashboards.

---

## Development

```bash
# Install Python dependencies
uv sync

# Run just infrastructure
docker compose up redis timescaledb -d

# Run dashboard locally (with hot reload)
uv run uvicorn dashboard.main:app --port 8000 --reload

# Run AI worker locally
uv run python ai/consumer.py

# Run Go ingestion locally
cd ingestion && go run .

# Rust agent
cd agent && cargo build --release && ./target/release/agent
```

See [`docs/TECHNICAL_DEV_GUIDE.md`](docs/TECHNICAL_DEV_GUIDE.md) for full internals documentation.

---

## How the Feedback Loop Works

```
User labels an anomaly in the dashboard
        │
        ▼
POST /api/feedback  {label: "false_positive"}
        │
        ▼
Feedback handler (feedback/handler.py)
  ├─ Persists label to TimescaleDB
  ├─ Reads ensemble weights from Redis
  ├─ false_positive  → lower IsolationForest sensitivity
  │  true_anomaly    → raise IsolationForest sensitivity
  │  expected_change → reset agent baseline
  └─ Saves updated weights to Redis
        │
        ▼
AI worker reads weights on next inference cycle
```

---

## Roadmap

- [ ] Model persistence across container restarts
- [ ] Kubernetes deployment with HPA
- [ ] Multi-model weighted ensemble voting
- [ ] Alert escalation tiers (P1/P2/P3)
- [ ] Grafana pre-built dashboard provisioning
- [ ] OpenTelemetry distributed tracing
- [ ] TimescaleDB automated compression policies

---

## License

MIT © 2026 — see [LICENSE](LICENSE)

---

> ⚠️ **Security note:** Never commit `.env`. It is listed in `.gitignore`. Use `.env.example` as a template and keep real credentials out of version control.
