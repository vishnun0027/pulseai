"""
ai/consumer.py
Redis Stream worker — orchestrates the full inference pipeline.
Reads telemetry from the Redis Stream, scores via IsolationForest + SHAP,
publishes scored events to Pub/Sub, and persists anomalies to TimescaleDB.
"""

import asyncio
import json
import os
import sys
import time
from typing import Dict

import redis.asyncio as aioredis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.features import FeatureEngineer
from ai.model import AnomalyModel
from ai.explainer import AnomalyExplainer
from ai.metrics import (
    inc_processed,
    inc_anomaly,
    inc_drift,
    observe_score,
    inc_training,
    start_metrics_server,
)
from baseline.drift_classifier import DriftDetector
from storage.db import init_pool, close_pool, execute, run_migrations
from storage.logging_config import setup_logger

# Wait for potential shared module conflicts
logger = setup_logger(__name__, "logs/ai_consumer.log")


# ─────────────────────────────────────────────────────────────────────────────
# DB persistence helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _persist_anomaly(event: dict) -> None:
    """Insert one scored event into the anomaly_events hypertable."""
    try:
        await execute(
            """
            INSERT INTO anomaly_events
                (agent_id, ts, cpu_usage, used_memory_gb,
                 anomaly_score, is_anomaly, drift_detected, explanation)
            VALUES ($1, to_timestamp($2), $3, $4, $5, $6, $7, $8::jsonb)
            """,
            event["agent_id"],
            event["timestamp"],
            event["cpu"],
            event["memory"],
            event["anomaly_score"],
            event["is_anomaly"],
            event["drift_detected"],
            json.dumps(event.get("explanation", {})),
        )
    except Exception as exc:
        logger.warning(f"[DB] Failed to persist anomaly event: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Per-Agent State Management
# ─────────────────────────────────────────────────────────────────────────────


class AgentState:
    def __init__(self, window_size: int = 5):
        self.engineer = FeatureEngineer(window_size=window_size)
        self.detector = DriftDetector()


# ─────────────────────────────────────────────────────────────────────────────
# Main consumer loop (Fully Async)
# ─────────────────────────────────────────────────────────────────────────────


async def run_consumer_async() -> None:
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))

    # Use async Redis client
    r = aioredis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    # Note: Model remains global for now, but per-agent feature/drift trackers are used.
    # Future enhancement: Per-agent models.
    model = AnomalyModel(contamination=0.1, threshold=-0.1)
    explainer = AnomalyExplainer(model.model)

    # Dictionary to maintain state per agent (fixes cross-contamination)
    agent_states: Dict[str, AgentState] = {}

    stream_name = "telemetry_stream"
    pubsub_channel = "anomalies_feed"

    # Start Prometheus metrics exporter (runs in background thread)
    start_metrics_server()

    # Initialise DB pool and run migrations
    db_available = False
    try:
        await init_pool()
        await run_migrations()
        logger.info("[Consumer] DB connection pool and migrations ready.")
        db_available = True
    except Exception as exc:
        logger.warning(
            f"[Consumer] DB unavailable — running without persistence: {exc}"
        )

    logger.info(f"[Consumer] Subscribing to Redis Stream '{stream_name}'...")

    last_id = "$"  # Read new messages only

    try:
        while True:
            try:
                # XREAD is now awaited
                result = await r.xread({stream_name: last_id}, count=10, block=1000)
                if result:
                    for stream, messages in result:
                        for message_id, data in messages:
                            last_id = message_id

                            payload_str = data.get("payload")
                            if not payload_str:
                                continue

                            payload = json.loads(payload_str)
                            agent_id = payload.get("agent_id", "unknown")

                            # Get or create per-agent state
                            if agent_id not in agent_states:
                                logger.info(
                                    f"[Consumer] New agent detected: {agent_id}. Initializing local state."
                                )
                                agent_states[agent_id] = AgentState()

                            state = agent_states[agent_id]

                            # Process with per-agent engineer
                            feats_dict = state.engineer.process(payload)
                            fvec = state.engineer.get_feature_vector(feats_dict)

                            was_trained = model.is_trained
                            model.train_or_update(fvec)

                            if model.is_trained:
                                # Rebuild explainer when model first becomes ready
                                if not was_trained or explainer.explainer is None:
                                    explainer.update_explainer()
                                    inc_training()

                                score = model.score(fvec)
                                observe_score(score)

                                # Process with per-agent drift detector
                                drift = state.detector.check_drift(
                                    feats_dict["cpu_mean_5"], feats_dict["mem_raw"]
                                )

                                is_anomaly = model.is_anomaly(score)
                                if is_anomaly:
                                    inc_anomaly()
                                if drift:
                                    inc_drift()

                                explanation: dict = {}
                                if is_anomaly:
                                    explanation = explainer.explain(fvec)

                                out_data = {
                                    "agent_id": agent_id,
                                    "timestamp": payload.get(
                                        "timestamp", int(time.time())
                                    ),
                                    "cpu": payload.get("metrics", {}).get(
                                        "cpu_usage", 0.0
                                    ),
                                    "memory": float(
                                        payload.get("metrics", {}).get("used_memory", 0)
                                    )
                                    / 1e9,
                                    "anomaly_score": round(score, 3),
                                    "is_anomaly": is_anomaly,
                                    "drift_detected": drift,
                                    "explanation": explanation,
                                }

                                # Publish to dashboard via Pub/Sub (awaited)
                                await r.publish(pubsub_channel, json.dumps(out_data))

                                inc_processed()

                                # Persist to TimescaleDB (awaited, non-blocking in single loop)
                                if db_available:
                                    await _persist_anomaly(out_data)

                                logger.info(
                                    f"[Intelligence] Agent: {agent_id} | "
                                    f"CPU: {out_data['cpu']:.1f}% | "
                                    f"Anomaly: {is_anomaly} | "
                                    f"Score: {out_data['anomaly_score']}"
                                )

            except Exception as exc:
                logger.error(f"[Consumer] Loop Error: {exc}")
                await asyncio.sleep(1)

    finally:
        # Cleanup
        await r.aclose()
        await close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(run_consumer_async())
    except KeyboardInterrupt:
        pass
