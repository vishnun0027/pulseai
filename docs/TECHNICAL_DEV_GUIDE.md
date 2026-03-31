# PulseAI — Technical Developer Guide

**Project:** PulseAI — AI-Based Self-Learning System Behavior Anomaly Detection  
**Version:** 2.0.0  
**Date:** 2026-03-31  
**Status:** Production-ready (Phase 1–5 complete)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Deep Dive](#2-architecture-deep-dive)
3. [Service Specifications](#3-service-specifications)
4. [Data Flow](#4-data-flow)
5. [Data Models & Schemas](#5-data-models--schemas)
6. [AI / ML Pipeline](#6-ai--ml-pipeline)
7. [Storage Layer](#7-storage-layer)
8. [Feedback Loop](#8-feedback-loop)
9. [REST API Reference](#9-rest-api-reference)
10. [Configuration Reference](#10-configuration-reference)
11. [Observability](#11-observability)
12. [Development Guide](#12-development-guide)
13. [Deployment Guide](#13-deployment-guide)
14. [Known Limitations & Future Work](#14-known-limitations--future-work)

---

## 1. System Overview

The Anomaly Intelligence System is a distributed, polyglot platform that continuously monitors the runtime behavior of system agents (CPU, memory, GPU, environment), detects anomalies using unsupervised machine learning, explains detections using SHAP feature attribution, and learns from user feedback to self-improve over time.

### Key Properties

| Property | Value |
|---|---|
| Languages | Rust (agent), Go (ingestion/correlation/alerts), Python (AI/dashboard) |
| Message transport | Redis Streams (telemetry), Redis Pub/Sub (anomalies, alerts) |
| Persistence | TimescaleDB (PostgreSQL 16 + TimescaleDB extension) |
| ML algorithm | IsolationForest (unsupervised) + ADWIN (drift) |
| Explainability | SHAP TreeExplainer |
| Web framework | FastAPI + Server-Sent Events |
| Containerization | Docker Compose (10 services) |
| Observability | Prometheus + Grafana |

---

## 2. Architecture Deep Dive

### 2.1 High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DATA COLLECTION LAYER                                                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Rust Agent (agent/)                                             │   │
│  │  · collector.rs  → sysinfo polling every 5s                     │   │
│  │  · environment.rs → WSL / Docker / bare-metal detection         │   │
│  │  · state_manager.rs → persistent boot count & session token     │   │
│  │  · gap_detector.rs → sleep/crash gap inference                  │   │
│  │  · main.rs → tokio async loop → HTTP POST to ingestion          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP POST /v1/telemetry (JSON)
┌────────────────────────────────────▼────────────────────────────────────┐
│  INGESTION LAYER                                                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Go Ingestion Service (ingestion/)                               │   │
│  │  · routes.go  → validates payload, calls dedup, XADD to stream  │   │
│  │  · dedup.go   → in-memory mutex map (agent_id + timestamp key)  │   │
│  │  · schemas.go → AgentPayload struct with SystemMetrics embed     │   │
│  │  · metrics.go → Prometheus counters exposed at /metrics         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                     │ XADD telemetry_stream              │
└────────────────────────────────────▼────────────────────────────────────┘
                              ┌────────────┐
                              │   Redis 7  │ ◄── Pub/Sub: anomalies_feed
                              │  Streams + │         cluster_alerts
                              │   Pub/Sub  │         baseline_reset_commands
                              │   Broker   │         feedback_events
                              └─────┬──────┘
                                    │ XREAD (blocking)
┌───────────────────────────────────▼─────────────────────────────────────┐
│  INTELLIGENCE LAYER                                                     │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Python AI Worker (ai/)                                          │   │
│  │  · features.py    → rolling window stats (mean/std/raw)         │   │
│  │  · model.py       → IsolationForest, buffer-trained online      │   │
│  │  · explainer.py   → SHAP TreeExplainer on trained model         │   │
│  │  · drift_detector.py → ADWIN per feature channel                │   │
│  │  · consumer.py    → orchestrates full pipeline + persists to DB │   │
│  │  · metrics.py     → Prometheus HTTP server on :9090             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Baseline Manager (baseline/)                                    │   │
│  │  · baseline_manager.py → per-agent z-score profile (100 samples)│   │
│  │  · drift_classifier.py → ADWIN on raw CPU/mem channels          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└───────────┬───────────────────────────────┬─────────────────────────────┘
            │ PUBLISH anomalies_feed         │ INSERT INTO anomaly_events
            │                               ▼
┌───────────▼────────────┐        ┌────────────────────┐
│ Go Correlation Engine  │        │   TimescaleDB      │
│ (correlation/)         │        │   · telemetry_     │
│ sliding 30s window     │        │     snapshots      │
│ ≥2 agents → cluster    │        │   · anomaly_events │
│ alert published        │        │   · feedback_labels│
└───────────┬────────────┘        └────────────────────┘
            │ PUBLISH cluster_alerts
┌───────────▼────────────┐
│ Go Alert Dispatcher    │
│ (alerts/)              │
│ Slack/Teams webhook    │
│ per ALERT_WEBHOOK_URL  │
└────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                                      │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Dashboard (dashboard/)                                   │   │
│  │  · main.py    → lifespan DB pool + router mount + static serve   │   │
│  │  · routes.py  → /api/stream (SSE), /api/anomalies, /api/agents  │   │
│  │               → /api/anomalies/{id}, /api/feedback, /api/health  │   │
│  │  · static/    → Chart.js UI with SHAP bars, feedback form,       │   │
│  │                  historical anomaly browser with date filters     │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  Feedback Handler (feedback/)                                     │   │
│  │  · handler.py → receive label → adjust IF weights in Redis       │   │
│  │               → persist to feedback_labels table                 │   │
│  │               → publish baseline_reset for expected_change       │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY LAYER                                                     │
│  Prometheus (:9091) → scrapes Go :8080/metrics + Python :9090/metrics   │
│  Grafana (:3000)    → visualizes all Prometheus metrics                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Network Topology (Docker Compose)

All services share the `projectsys_default` bridge network. Service discovery uses Docker DNS names (e.g., `redis`, `timescaledb`, `ingestion`).

| Container Name | Internal DNS | External Port |
|---|---|---|
| `redis-broker` | `redis` | 6379 |
| `timescaledb` | `timescaledb` | 5433 (maps to internal 5432) |
| `ingestion-api` | `ingestion` | 8080 |
| `ai-worker` | `ai-consumer` | 9090 |
| `web-dashboard` | `dashboard` | 8000 |
| `prometheus` | `prometheus` | 9091 |
| `grafana` | `grafana` | 3000 |

---

## 3. Service Specifications

### 3.1 Rust Agent

**Entry:** `agent/src/main.rs`  
**Runtime:** tokio async, 5-second poll loop  
**Dependencies:** sysinfo, reqwest, serde, tokio

**Telemetry payload (JSON):**

```json
{
  "agent_id": "agent-<hostname-hash>",
  "timestamp": 1774932632,
  "metrics": {
    "cpu_usage": 26.49,
    "total_memory": 8192000000,
    "used_memory": 3450000000,
    "load_average_1m": 1.2,
    "gpu_usage": null
  },
  "environment": {
    "env_type": "docker",
    "os_version": "Ubuntu 24.04"
  },
  "session": {
    "session_token": "abc123",
    "boot_count": 5
  },
  "gap_type": "none"
}
```

**Gap types:** `none` | `short` (< 60s) | `long` (≥ 60s)  
**Environment types:** `host` | `docker` | `wsl` | `unknown`

### 3.2 Go Ingestion Service

**Entry:** `ingestion/main.go`  
**Runtime:** `net/http` standard library  
**Port:** 8080

**Deduplication:** Composite key `agent_id + ":" + timestamp` stored in a mutex-protected `map[string]bool`. Max 10,000 entries (configurable via `dedup_max_entries`).

**Redis Stream format:**
```
XADD telemetry_stream * payload <json-encoded-AgentPayload>
```

**Prometheus metrics endpoint:** `GET /metrics`

### 3.3 Python AI Worker

**Entry:** `ai/consumer.py`  
**Runtime:** Synchronous main loop + asyncio for DB writes

**Pipeline per message:**
1. `FeatureEngineer.process(payload)` → rolling window stats
2. `AnomalyModel.train_or_update(feature_vector)` → buffer 20 samples then fit
3. If model trained: `AnomalyModel.score(fvec)` → inverted decision function
4. `DriftDetector.check_drift(cpu_mean, mem_raw)` → ADWIN per channel
5. If anomaly: `AnomalyExplainer.explain(fvec)` → SHAP values dict
6. `redis.publish("anomalies_feed", json)` → dashboard SSE
7. `asyncio.run(_persist_anomaly(event))` → TimescaleDB INSERT
8. Prometheus counters incremented

**Prometheus metrics server:** `:9090/metrics` (separate thread)

### 3.4 Go Correlation Engine

**Entry:** `correlation/main.go` + `correlator.go`  
**Logic:** Maintains in-memory sliding window (default 30s) of `(agent_id, timestamp)` tuples from `anomalies_feed`. When the count of distinct agents within the window reaches `cluster_min_agents` (default 2), publishes a cluster alert to `cluster_alerts` channel.

### 3.5 Go Alert Dispatcher

**Entry:** `alerts/main.go` + `alerter.go`  
**Subscriptions:** `anomalies_feed`, `cluster_alerts`  
**Output:** HTTP POST to `ALERT_WEBHOOK_URL` with JSON body  
**Threshold:** Only fires when `anomaly_score > severity_threshold` (default 0.1)

### 3.6 FastAPI Dashboard

**Entry:** `dashboard/main.py`  
**Framework:** FastAPI with `lifespan` context manager  
**Frontend:** Vanilla HTML/CSS/JS with Chart.js  
**Real-time:** Server-Sent Events from Redis Pub/Sub subscription

---

## 4. Data Flow

### 4.1 Normal Telemetry Flow

```
Rust Agent
  │
  │  HTTP POST /v1/telemetry  (every 5s)
  ▼
Go Ingestion
  ├─ Validate JSON
  ├─ Check dedup cache (drop if duplicate)
  ├─ XADD → Redis Stream "telemetry_stream"
  └─ Increment Prometheus counters
         │
         │  XREAD (blocking, batch 10)
         ▼
Python AI Worker
  ├─ Extract features (rolling window)
  ├─ Train model if buffer ≥ 20 samples
  ├─ Score → anomaly_score (float)
  ├─ Check ADWIN drift (per feature)
  ├─ If anomaly: SHAP explain
  ├─ PUBLISH → Redis "anomalies_feed" (JSON event)
  ├─ INSERT → TimescaleDB anomaly_events
  └─ Update Prometheus histograms/counters
         │
         ├─── SUB by Go Correlation Engine
         │        └─ If cluster → PUBLISH "cluster_alerts"
         │
         ├─── SUB by Go Alert Dispatcher
         │        └─ If score > threshold → POST webhook
         │
         └─── SUB by FastAPI Dashboard
                  └─ SSE push to connected browsers
```

### 4.2 Feedback Flow

```
User (browser)
  │
  │  POST /api/feedback  {agent_id, label, note}
  ▼
FastAPI /api/feedback endpoint
  ▼
feedback/handler.py :: process_feedback()
  ├─ INSERT → TimescaleDB feedback_labels
  ├─ Load ensemble weights from Redis
  ├─ Adjust weights:
  │     false_positive   → isolation_forest weight -0.05
  │     true_anomaly     → isolation_forest weight +0.02
  │     expected_change  → weights unchanged
  ├─ Save updated weights to Redis (no TTL)
  └─ If expected_change:
       PUBLISH → Redis "baseline_reset_commands"
         └─ baseline_manager listens and resets rolling window
```

---

## 5. Data Models & Schemas

### 5.1 Telemetry Payload (Rust → Go)

```go
type AgentPayload struct {
    AgentID     string         `json:"agent_id"`
    Timestamp   uint64         `json:"timestamp"`
    Metrics     SystemMetrics  `json:"metrics"`
    Environment EnvironmentInfo `json:"environment"`
    Session     SessionState   `json:"session"`
    GapType     string         `json:"gap_type"`
}

type SystemMetrics struct {
    CpuUsage      float64  `json:"cpu_usage"`
    TotalMemory   uint64   `json:"total_memory"`
    UsedMemory    uint64   `json:"used_memory"`
    LoadAverage1m float64  `json:"load_average_1m"`
    GpuUsage      *float32 `json:"gpu_usage,omitempty"`
}
```

### 5.2 Scored Event (Go → Python → Dashboard)

```json
{
  "agent_id": "agent-00d02558c329",
  "timestamp": 1774932632,
  "cpu": 26.49,
  "memory": 3.45,
  "anomaly_score": 0.123,
  "is_anomaly": true,
  "drift_detected": false,
  "explanation": {
    "cpu_mean_5": 0.081,
    "cpu_std_5": 0.042,
    "mem_raw": -0.023
  }
}
```

### 5.3 Feature Vector

Produced by `ai/features.py`. Five features per window of 5 samples:

| Feature | Description |
|---|---|
| `cpu_mean_5` | Rolling mean of CPU usage over last 5 samples |
| `cpu_std_5` | Rolling std deviation of CPU usage |
| `mem_raw` | Current memory usage in GB |
| `mem_mean_5` | Rolling mean of memory usage |
| `load_mean_5` | Rolling mean of load average |

### 5.4 Database Tables

#### `telemetry_snapshots` (Hypertable on `ts`)
```sql
agent_id        TEXT        NOT NULL
ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
cpu_usage       DOUBLE PRECISION
used_memory_gb  DOUBLE PRECISION
load_avg_1m     DOUBLE PRECISION
gpu_usage       DOUBLE PRECISION
env_type        TEXT
gap_type        TEXT
```

#### `anomaly_events` (Hypertable on `ts`)
```sql
id              BIGSERIAL
agent_id        TEXT        NOT NULL
ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
cpu_usage       DOUBLE PRECISION
used_memory_gb  DOUBLE PRECISION
anomaly_score   DOUBLE PRECISION
is_anomaly      BOOLEAN
drift_detected  BOOLEAN
explanation     JSONB
UNIQUE (agent_id, ts)
```

Indexed on `(agent_id, ts DESC)` for fast per-agent lookups.

#### `feedback_labels`
```sql
id               BIGSERIAL PRIMARY KEY
anomaly_event_id BIGINT
agent_id         TEXT        NOT NULL
ts               TIMESTAMPTZ NOT NULL DEFAULT NOW()
label            TEXT        NOT NULL CHECK (label IN (
                   'false_positive','true_anomaly','expected_change'))
note             TEXT
```

### 5.5 Pydantic API Models (`storage/models.py`)

```python
class AnomalyEvent(BaseModel):
    id: Optional[int]
    agent_id: str
    ts: datetime
    cpu_usage: float
    used_memory_gb: float
    anomaly_score: float
    is_anomaly: bool
    drift_detected: bool
    explanation: Dict[str, Any]

class FeedbackCreate(BaseModel):
    anomaly_event_id: Optional[int]
    agent_id: str
    label: Literal["false_positive","true_anomaly","expected_change"]
    note: Optional[str]

class AgentSummary(BaseModel):
    agent_id: str
    total_events: int
    anomaly_count: int
    last_seen: Optional[datetime]
    anomaly_rate: float   # 0.0–1.0
```

---

## 6. AI / ML Pipeline

### 6.1 IsolationForest Model

- **Algorithm:** sklearn `IsolationForest`  
- **Contamination:** 0.1 (10% expected anomaly rate — configurable)  
- **Training trigger:** Buffer of 20 samples accumulated, then `.fit()`. Buffer cleared after each retrain.  
- **Scoring:** `score = -model.decision_function(X)[0]` — higher = more anomalous  
- **Anomaly threshold:** `score > 0.0`

### 6.2 ADWIN Drift Detection

- **Library:** `river.drift.ADWIN`  
- **Channels:** One detector per feature channel (`cpu_mean_5`, `mem_raw`)  
- **Behavior:** Detects concept drift in the input distribution. On detection, flags `drift_detected=True` in the event payload.  
- **Independence from anomaly:** Drift ≠ anomaly. A drift can occur on normal data (e.g., workload shift).

### 6.3 SHAP Explainability

- **Explainer:** `shap.TreeExplainer(model)` — rebuilt whenever model is retrained  
- **Output:** Dict of `{feature_name: shap_value}` for the scored sample  
- **Sign convention:** Positive SHAP → feature pushed score toward anomaly; Negative → toward normal  
- **Only computed:** When `is_anomaly = True` (performance optimization)

### 6.4 Ensemble Weights (Feedback-Driven)

Stored in Redis key `feedback:ensemble_weights` as JSON:

```json
{
  "isolation_forest": 1.0,
  "zscore_baseline":  1.0,
  "drift_detector":   1.0
}
```

- `false_positive` → `isolation_forest -= 0.05` (floor 0.5)
- `true_anomaly` → `isolation_forest += 0.02` (ceiling 2.0)
- `expected_change` → no weight change; baseline reset triggered

> **Note:** The current consumer uses single-model IsolationForest. Ensemble weights are stored and exposed for future multi-model weighted voting (roadmap item).

### 6.5 Offline Training

```bash
uv run python -m ai.trainer path/to/telemetry.jsonl
```

Expects one JSON payload per line. Trains on full dataset, evaluates, saves to `models/isolation_forest.pkl`. The online consumer will load this model at startup if the file exists (future wiring).

---

## 7. Storage Layer

### 7.1 `storage/db.py` — Connection Pool

```python
# Initialize at startup (called in FastAPI lifespan + consumer boot)
await init_pool(min_size=2, max_size=10)

# Run schema migrations (idempotent — safe to call on every boot)
await run_migrations()

# Query helpers
rows = await fetch_all("SELECT * FROM anomaly_events WHERE agent_id = $1", agent_id)
row  = await fetch_one("SELECT * FROM anomaly_events WHERE id = $1", event_id)
status = await execute("INSERT INTO ...", *args)

# Shutdown
await close_pool()
```

Connection string built from env vars: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.

### 7.2 `storage/cache.py` — Redis Helpers

```python
# Async (FastAPI)
client = await get_async_client()
await cache_set(client, key, value, ttl_s=300)
data = await cache_get(client, key)     # Returns None on miss

# Sync (AI consumer)
client = get_sync_client()
cache_set_sync(client, key, value, ttl_s=0)   # ttl_s=0 → no expiry
data = cache_get_sync(client, key)

# Key namespaces (prevents typos across services)
CacheKeys.agent_summary("agent-abc")   → "agent_summary:agent-abc"
CacheKeys.feedback_weights()           → "feedback:ensemble_weights"
CacheKeys.dashboard_stats()            → "dashboard:stats"
```

---

## 8. Feedback Loop

### 8.1 Processing Logic (`feedback/handler.py`)

```python
async def process_feedback(fb: FeedbackCreate) -> dict:
    # 1. Persist label to DB
    record_id = await _persist_feedback(fb)

    # 2. Load weights from Redis
    weights = _load_weights(redis_client)

    # 3. Adjust weights
    if fb.label == "false_positive":
        weights["isolation_forest"] = clamp(weights["isolation_forest"] - 0.05, 0.5, 2.0)
    elif fb.label == "true_anomaly":
        weights["isolation_forest"] = clamp(weights["isolation_forest"] + 0.02, 0.5, 2.0)

    # 4. Save weights
    _save_weights(redis_client, weights)

    # 5. Baseline reset (expected_change only)
    if fb.label == "expected_change":
        redis_client.publish("baseline_reset_commands",
            json.dumps({"action": "reset_baseline", "agent_id": fb.agent_id}))

    return {"status": "accepted", "current_weights": weights, ...}
```

### 8.2 Baseline Reset Command

Published to `baseline_reset_commands` channel:
```json
{"action": "reset_baseline", "agent_id": "agent-abc123"}
```

The `BaselineManager` (future wiring) subscribes to this channel and clears the rolling window for the specified agent, allowing it to re-learn the new normal behavior.

---

## 9. REST API Reference

**Base URL:** `http://localhost:8000`

### `GET /api/stream`

Server-Sent Events stream of live scored telemetry.

**Response format:** One SSE event per scored telemetry frame.

```
data: {"agent_id":"agent-abc","timestamp":1774932632,"cpu":26.49,"memory":3.45,"anomaly_score":0.123,"is_anomaly":true,"drift_detected":false,"explanation":{"cpu_mean_5":0.081}}
```

---

### `GET /api/anomalies`

Paginated list of anomaly events from TimescaleDB.

**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `agent_id` | string | — | Filter by agent ID |
| `only_anomalies` | bool | false | Return only rows where `is_anomaly=true` |
| `limit` | int | 50 | Page size (max 500) |
| `offset` | int | 0 | Page offset |
| `from_ts` | ISO 8601 | — | Start of time range |
| `to_ts` | ISO 8601 | — | End of time range |

**Response:**
```json
{
  "total": 1423,
  "items": [
    {
      "id": 42,
      "agent_id": "agent-abc",
      "ts": "2026-03-31T05:01:15.000Z",
      "cpu_usage": 87.3,
      "used_memory_gb": 6.2,
      "anomaly_score": 0.312,
      "is_anomaly": true,
      "drift_detected": false,
      "explanation": {"cpu_mean_5": 0.21, "mem_raw": -0.04}
    }
  ]
}
```

---

### `GET /api/anomalies/{event_id}`

Single anomaly event with full SHAP explanation.

**Response:** Same shape as a single item from `/api/anomalies`.  
**404** if not found. **503** if DB unavailable.

---

### `GET /api/agents`

Per-agent aggregate statistics.

**Response:**
```json
[
  {
    "agent_id": "agent-abc",
    "total_events": 8640,
    "anomaly_count": 43,
    "anomaly_rate": 0.005,
    "last_seen": "2026-03-31T05:23:00.000Z"
  }
]
```

---

### `POST /api/feedback`

Submit a feedback label for the most recent anomaly event from an agent.

**Request body:**
```json
{
  "anomaly_event_id": 42,
  "agent_id": "agent-abc",
  "label": "false_positive",
  "note": "This was a scheduled backup job."
}
```

**Labels:** `false_positive` | `true_anomaly` | `expected_change`

**Response (201):**
```json
{
  "status": "accepted",
  "record_id": 7,
  "label": "false_positive",
  "agent_id": "agent-abc",
  "action": "IsolationForest weight reduced. Future sensitivity lowered.",
  "current_weights": {
    "isolation_forest": 0.95,
    "zscore_baseline": 1.0,
    "drift_detector": 1.0
  }
}
```

---

### `GET /api/health`

```json
{"status": "ok", "service": "anomaly-dashboard"}
```

---

## 10. Configuration Reference

**File:** `config/settings.toml`

```toml
[redis]
host             = "redis"              # Docker service name / hostname
port             = 6379
telemetry_stream = "telemetry_stream"   # Redis Stream for raw telemetry
anomalies_feed   = "anomalies_feed"     # Pub/Sub for scored events
feedback_channel = "feedback_events"    # Pub/Sub for feedback events

[database]
host     = "timescaledb"   # Docker service name / hostname
port     = 5432
user     = "anomaly"
password = "anomaly"
name     = "anomalydb"
pool_min = 2               # asyncpg min pool connections
pool_max = 10              # asyncpg max pool connections

[ingestion]
host             = "0.0.0.0"
port             = 8080
dedup_max_entries = 10000  # Max entries in in-memory dedup cache

[dashboard]
host = "0.0.0.0"
port = 8000

[agent]
telemetry_url   = "http://ingestion:8080/v1/telemetry"
poll_interval_s = 5

[ml]
isolation_forest_contamination = 0.1   # Expected anomaly fraction
feature_window_size            = 5     # Rolling window size for features
baseline_min_samples           = 20    # Min samples before model trains

[alerts]
webhook_url        = ""      # Slack/Teams/Discord webhook URL
enabled            = false
severity_threshold = 0.1     # Min score before alert fires

[correlation]
cluster_window_s   = 30      # Seconds to group multi-agent anomalies
cluster_min_agents = 2       # Min distinct agents to trigger cluster alert
```

**Environment variable overrides** (take precedence over `settings.toml`):

| Env Var | Service | Purpose |
|---|---|---|
| `REDIS_HOST` | All | Redis hostname |
| `REDIS_PORT` | All | Redis port |
| `DB_HOST` | ai-worker, dashboard | TimescaleDB hostname |
| `DB_PORT` | ai-worker, dashboard | TimescaleDB port |
| `DB_USER` | ai-worker, dashboard | DB username |
| `DB_PASSWORD` | ai-worker, dashboard | DB password |
| `DB_NAME` | ai-worker, dashboard | Database name |
| `ALERT_WEBHOOK_URL` | alerter | Webhook destination |
| `TELEMETRY_URL` | agent | Ingestion HTTP endpoint |
| `METRICS_PORT` | ai-worker | Prometheus exporter port (default 9090) |

---

## 11. Observability

### 11.1 Prometheus Metrics

**Scrape config:** `config/prometheus.yml`

**Go ingestion** (`http://ingestion:8080/metrics`):

| Metric | Type | Description |
|---|---|---|
| `ingestion_telemetry_received_total` | Counter | All POST requests to /v1/telemetry |
| `ingestion_telemetry_accepted_total` | Counter | Payloads forwarded to Redis |
| `ingestion_telemetry_duplicated_total` | Counter | Payloads dropped by dedup |
| `ingestion_redis_errors_total` | Counter | Redis XADD errors |
| `ingestion_dedup_cache_size` | Gauge | Current dedup cache size |

**Python AI worker** (`http://ai-consumer:9090/metrics`):

| Metric | Type | Description |
|---|---|---|
| `ai_inference_processed_total` | Counter | Events fully processed |
| `ai_anomalies_detected_total` | Counter | Events classified anomalous |
| `ai_drift_detected_total` | Counter | ADWIN drift detections |
| `ai_anomaly_score` | Histogram | Score distribution (10 buckets) |
| `ai_model_training_events_total` | Counter | Model retrain events |
| `ai_feedback_events_total{label}` | Counter | Feedback per label type |

### 11.2 Grafana Setup

**URL:** `http://localhost:3000`  
**Default credentials:** `admin` / `anomaly`

To add the Prometheus data source:
1. Go to **Configuration → Data Sources → Add data source**
2. Select **Prometheus**
3. URL: `http://prometheus:9090`
4. Click **Save & Test**

**Suggested dashboard panels:**
- Ingestion rate: `rate(ingestion_telemetry_received_total[1m])`
- Anomaly rate: `rate(ai_anomalies_detected_total[5m])`
- Score distribution: Histogram from `ai_anomaly_score`
- Drift events: `rate(ai_drift_detected_total[5m])`
- Dedup cache: `ingestion_dedup_cache_size`

---

## 12. Development Guide

### 12.1 Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Docker | ≥ 24.0 | Container runtime |
| Docker Compose | ≥ 2.20 | Orchestration |
| uv | latest | Python package manager |
| Rust toolchain | stable | Agent development |
| Go | ≥ 1.22 | Go service development |
| Python | ≥ 3.12 | AI/dashboard development |

### 12.2 Python Environment

```bash
# Create and sync venv
uv sync

# Activate
source .venv/bin/activate

# Add a new dependency
uv add <package>
```

Key development dependencies (auto-included via `uv sync`):
- `asyncpg` — async PostgreSQL/TimescaleDB
- `pydantic` — data validation
- `prometheus-client` — metrics
- `river` — ADWIN drift detection
- `shap` — explainability
- `scikit-learn` — IsolationForest

### 12.3 Running Services Locally (no Docker)

```bash
# Start infrastructure only
docker run -d -p 6379:6379 --name redis redis:7-alpine
docker run -d -p 5432:5432 --name tsdb \
  -e POSTGRES_USER=anomaly -e POSTGRES_PASSWORD=anomaly -e POSTGRES_DB=anomalydb \
  timescale/timescaledb:latest-pg16

# Python dashboard
uv run uvicorn dashboard.main:app --host 0.0.0.0 --port 8000 --reload

# Python AI consumer
uv run python ai/consumer.py

# Go ingestion
cd ingestion && go run .

# Rust agent
cd agent && cargo run
```

### 12.4 Adding a New API Endpoint

1. Add the route function to `dashboard/routes.py`
2. Use `fetch_all` / `fetch_one` from `storage/db.py` for DB queries
3. Use `cache_get` / `cache_set` from `storage/cache.py` for Redis caching
4. Add the Pydantic response model to `storage/models.py`
5. Restart dashboard: `docker compose restart dashboard`

### 12.5 Adding a New Prometheus Metric (Python)

```python
# In ai/metrics.py
from prometheus_client import Counter
my_counter = Counter("ai_my_event_total", "Description")

# Expose helper
def inc_my_event():
    my_counter.inc()

# In consumer.py
from ai.metrics import inc_my_event
inc_my_event()
```

### 12.6 Adding a New Prometheus Metric (Go)

```go
// In ingestion/metrics.go
var myCounter = prometheus.NewCounter(prometheus.CounterOpts{
    Name: "ingestion_my_event_total",
    Help: "Description.",
})

func init() {
    prometheus.MustRegister(myCounter)
}

// In routes.go or wherever needed:
myCounter.Inc()
```

### 12.7 Testing

**Inject a telemetry payload manually:**

```bash
curl -X POST http://localhost:8080/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent-001",
    "timestamp": 1774932700,
    "metrics": {"cpu_usage": 95.0,"total_memory":8000000000,"used_memory":7500000000,"load_average_1m":4.5},
    "environment": {"env_type":"host","os_version":"Ubuntu 24.04"},
    "session": {"session_token":"abc","boot_count":1},
    "gap_type": "none"
  }'
```

**Check anomaly events in DB:**

```bash
docker exec timescaledb psql -U anomaly -d anomalydb \
  -c "SELECT agent_id, ts, cpu_usage, anomaly_score, is_anomaly FROM anomaly_events ORDER BY ts DESC LIMIT 10;"
```

**Check feedback weights in Redis:**

```bash
docker exec redis-broker redis-cli GET "feedback:ensemble_weights"
```

**Verify Prometheus metrics:**

```bash
curl http://localhost:9090/metrics | grep ai_anomalies
curl http://localhost:8080/metrics | grep ingestion_telemetry
```

---

## 13. Deployment Guide

### 13.1 Docker Compose (Single Node)

```bash
# Full build and start
docker compose up --build -d

# Rebuild only changed services (faster)
docker compose build dashboard ai-consumer
docker compose up -d

# View logs
docker compose logs -f ai-consumer dashboard

# Stop all
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v
```

### 13.2 Environment Configuration

Copy `.env.example` to `.env` and set:

```env
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
```

### 13.3 Port Summary

| Service | External Port | Protocol |
|---|---|---|
| Dashboard | 8000 | HTTP |
| Ingestion API | 8080 | HTTP |
| AI Prometheus | 9090 | HTTP |
| Prometheus UI | 9091 | HTTP |
| Grafana | 3000 | HTTP |
| Redis | 6379 | Redis |
| TimescaleDB | 5433 | PostgreSQL |

### 13.4 Health Checks

```bash
# All services status
docker compose ps

# Individual health
curl http://localhost:8000/api/health
curl http://localhost:8080/metrics | head -5
docker exec redis-broker redis-cli ping
docker exec timescaledb pg_isready -U anomaly -d anomalydb
```

### 13.5 Data Retention

TimescaleDB supports automatic data retention policies. To add a 30-day retention on anomaly events:

```sql
SELECT add_retention_policy('anomaly_events', INTERVAL '30 days');
SELECT add_retention_policy('telemetry_snapshots', INTERVAL '7 days');
```

Run inside the container:

```bash
docker exec timescaledb psql -U anomaly -d anomalydb -c \
  "SELECT add_retention_policy('anomaly_events', INTERVAL '30 days');"
```

---

## 14. Known Limitations & Future Work

### Current Limitations

| Area | Limitation |
|---|---|
| **Model persistence** | IsolationForest is retrained in-memory; model does not survive container restart |
| **Ensemble weights** | Weights are stored in Redis but the consumer uses single-model scoring; multi-model voting is scaffolded but not yet wired |
| **gRPC** | Proto files (`snapshot.proto`, `alert.proto`) are defined but ingestion uses HTTP/JSON instead |
| **TimescaleDB FK** | `feedback_labels.anomaly_event_id` is a plain `BIGINT` (no FK constraint) due to hypertable primary key restrictions |
| **Baseline reset** | `baseline_reset_commands` Pub/Sub channel is published but the consumer is not yet subscribed |
| **Authentication** | No API auth (assumes trusted network / firewall-protected deployment) |

### Planned Future Work (Phase 6+)

| Feature | Description |
|---|---|
| **Model persistence** | Save/load IsolationForest to `models/` directory on retrain |
| **Kubernetes deployment** | Helm chart with HPA for ingestion and AI workers |
| **Multi-model ensemble** | Weighted voting across IsolationForest, One-Class SVM, Autoencoder |
| **Alert escalation tiers** | Score-based tier 1/2/3 severity with escalation delays |
| **Grafana provisioning** | Pre-built dashboard JSON for zero-config Grafana setup |
| **OpenTelemetry tracing** | Distributed trace from ingestion → Redis → AI worker |
| **Anonymization** | GDPR-friendly agent ID hashing option |
| **TimescaleDB compression** | Automatic chunk compression after 7 days |
| **Email alerts** | SMTP support alongside webhook |
