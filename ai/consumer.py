"""
ai/consumer.py
Redis Stream worker — orchestrates the full inference pipeline.
Reads telemetry from the Redis Stream, scores via IsolationForest + SHAP,
publishes scored events to Pub/Sub, and persists anomalies to TimescaleDB.
"""

import asyncio
import json
import logging
import os
import sys
import time

import redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.features import FeatureEngineer
from ai.model import AnomalyModel
from ai.explainer import AnomalyExplainer
from ai.metrics import (
    inc_processed, inc_anomaly, inc_drift,
    observe_score, inc_training,
    start_metrics_server,
)
from baseline.drift_classifier import DriftDetector
from storage.db import init_pool, close_pool, execute, run_migrations
from storage.logging_config import setup_logger

logger = setup_logger(__name__, "logs/ai_consumer.log")


# ─────────────────────────────────────────────────────────────────────────────
# DB persistence helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _init_db() -> None:
    """Boot DB pool and run schema migrations once."""
    await init_pool()
    await run_migrations()


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
# Main consumer loop (sync Redis I/O + async DB writes via asyncio.run)
# ─────────────────────────────────────────────────────────────────────────────

def run_consumer() -> None:
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    engineer = FeatureEngineer(window_size=5)
    model = AnomalyModel(contamination=0.1, threshold=-0.1)
    explainer = AnomalyExplainer(model.model)
    detector = DriftDetector()

    stream_name = "telemetry_stream"
    pubsub_channel = "anomalies_feed"

    # Start Prometheus metrics exporter
    start_metrics_server()

    # Initialise DB pool once (sync wrapper around async init)
    db_available = False
    db_loop = None
    try:
        asyncio.run(_init_db())
        logger.info("[Consumer] DB pool ready.")
        db_available = True
    except Exception as exc:
        logger.warning(f"[Consumer] DB unavailable — running without persistence: {exc}")

    logger.info(f"[Consumer] Subscribing to Redis Stream '{stream_name}'...")

    last_id = "$"  # Read new messages only

    while True:
        try:
            result = r.xread({stream_name: last_id}, count=10, block=0)
            if result:
                for stream, messages in result:
                    for message_id, data in messages:
                        last_id = message_id

                        payload_str = data.get("payload")
                        if not payload_str:
                            continue

                        payload = json.loads(payload_str)

                        feats_dict = engineer.process(payload)
                        fvec = engineer.get_feature_vector(feats_dict)

                        was_trained = model.is_trained
                        model.train_or_update(fvec)

                        if model.is_trained:
                            # Rebuild explainer when model first becomes ready
                            if not was_trained or explainer.explainer is None:
                                explainer.update_explainer()
                                inc_training()

                            score = model.score(fvec)
                            observe_score(score)
                            drift = detector.check_drift(
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
                                "agent_id": payload.get("agent_id", "unknown"),
                                "timestamp": payload.get("timestamp", int(time.time())),
                                "cpu": payload.get("metrics", {}).get("cpu_usage", 0.0),
                                "memory": float(
                                    payload.get("metrics", {}).get("used_memory", 0)
                                ) / 1e9,
                                "anomaly_score": round(score, 3),
                                "is_anomaly": is_anomaly,
                                "drift_detected": drift,
                                "explanation": explanation,
                            }

                            # Publish to dashboard via Pub/Sub
                            r.publish(pubsub_channel, json.dumps(out_data))

                            inc_processed()

                            # Persist to TimescaleDB (best-effort)
                            if db_available:
                                try:
                                    # Use create_task to avoid blocking, schedule persistence async
                                    asyncio.run(_persist_anomaly(out_data))
                                except RuntimeError as e:
                                    if "Event loop is closed" in str(e):
                                        logger.debug("[DB] Event loop issue on persist, skipping this event")
                                    else:
                                        logger.warning(f"[DB] Persistence error: {e}")

                            logger.info(
                                f"[Intelligence] Agent: {out_data['agent_id']} | "
                                f"CPU: {out_data['cpu']:.1f}% | "
                                f"Anomaly: {is_anomaly} | "
                                f"Score: {out_data['anomaly_score']}"
                            )

        except Exception as exc:
            logger.error(f"[Consumer] Error: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    run_consumer()
