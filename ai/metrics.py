"""
ai/metrics.py
Prometheus metrics for the Python AI inference worker.

Exposes:
  - inference_processed_total    Counter — events processed
  - anomalies_detected_total     Counter — events scored as anomalous
  - drift_detected_total         Counter — drift events fired
  - inference_score_histogram    Histogram — distribution of anomaly scores
  - model_training_events_total  Counter — how many times model was retrained

Usage (in consumer.py):
    from ai.metrics import (
        inc_processed, inc_anomaly, inc_drift,
        observe_score, inc_training,
        start_metrics_server,
    )
    start_metrics_server()   # call once at startup

The exporter binds to :9090/metrics by default (override with METRICS_PORT env var).
"""

import logging
import os
import threading

from prometheus_client import (
    Counter,
    Histogram,
    start_http_server,
)

logger = logging.getLogger(__name__)

# ── Metric declarations ────────────────────────────────────────────────────

inference_processed = Counter(
    "ai_inference_processed_total",
    "Total telemetry events processed by the AI inference pipeline.",
)

anomalies_detected = Counter(
    "ai_anomalies_detected_total",
    "Total events classified as anomalous by the model.",
)

drift_detected = Counter(
    "ai_drift_detected_total",
    "Total concept drift events detected by ADWIN.",
)

inference_score = Histogram(
    "ai_anomaly_score",
    "Distribution of anomaly scores from the IsolationForest model.",
    buckets=[-0.5, -0.2, -0.1, 0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0],
)

model_training_events = Counter(
    "ai_model_training_events_total",
    "Number of times the IsolationForest model was (re)trained.",
)

feedback_events = Counter(
    "ai_feedback_events_total",
    "Total feedback labels submitted by users.",
    ["label"],  # label dimension: false_positive | true_anomaly | expected_change
)

# ── Convenience helpers ────────────────────────────────────────────────────

def inc_processed() -> None:
    inference_processed.inc()


def inc_anomaly() -> None:
    anomalies_detected.inc()


def inc_drift() -> None:
    drift_detected.inc()


def observe_score(score: float) -> None:
    inference_score.observe(score)


def inc_training() -> None:
    model_training_events.inc()


def inc_feedback(label: str) -> None:
    feedback_events.labels(label=label).inc()


# ── HTTP metrics server ────────────────────────────────────────────────────

def start_metrics_server() -> None:
    """
    Start the Prometheus HTTP exporter in a background daemon thread.
    Binds to 0.0.0.0:METRICS_PORT (default 9090).
    """
    port = int(os.environ.get("METRICS_PORT", "9090"))
    try:
        start_http_server(port)
        logger.info(f"[Metrics] Prometheus exporter running on :{port}/metrics")
    except OSError as exc:
        logger.warning(f"[Metrics] Could not start exporter on :{port} — {exc}")
