"""
feedback/handler.py
Processes user feedback on anomaly events.

Feedback labels:
  - false_positive   → increase threshold / lower weight on this agent's model
  - true_anomaly     → reinforce; no model change needed
  - expected_change  → update baseline for the agent (controlled drift)

The handler:
  1. Persists the label to the feedback_labels DB table.
  2. Adjusts ensemble weights stored in Redis so the AI consumer uses them
     on the next inference cycle.
  3. For expected_change labels, publishes a baseline-reset command to
     a dedicated Redis channel that the baseline manager monitors.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import redis

from storage.db import execute, fetch_one, init_pool, run_migrations
from storage.cache import CacheKeys, cache_set_sync, cache_get_sync, get_sync_client
from storage.models import FeedbackCreate, FeedbackLabel
from storage.logging_config import setup_logger

logger = setup_logger(__name__, "logs/feedback.log")

# Redis channel baseline manager subscribes to
BASELINE_RESET_CHANNEL = "baseline_reset_commands"

# Default ensemble weights (used when no feedback has been submitted)
DEFAULT_WEIGHTS = {
    "isolation_forest": 1.0,
    "zscore_baseline": 1.0,
    "drift_detector": 1.0,
}

# How much to penalise / reward weights per feedback event
WEIGHT_PENALTY = 0.05   # false_positive  → reduce IF weight
WEIGHT_REWARD = 0.02    # true_anomaly    → (optionally boost, kept mild)
WEIGHT_MIN = 0.5        # floor
WEIGHT_MAX = 2.0        # ceiling


# ─────────────────────────────────────────────────────────────────────────────
# Weight management (stored in Redis, not DB — fast lookup by inference worker)
# ─────────────────────────────────────────────────────────────────────────────

def _load_weights(r: redis.Redis) -> dict:
    cached = cache_get_sync(r, CacheKeys.feedback_weights())
    if cached:
        return cached
    return dict(DEFAULT_WEIGHTS)


def _save_weights(r: redis.Redis, weights: dict) -> None:
    cache_set_sync(r, CacheKeys.feedback_weights(), weights, ttl_s=0)  # no expiry


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _adjust_weights(r: redis.Redis, label: FeedbackLabel) -> dict:
    """
    Mutate ensemble weights based on feedback label and persist to Redis.
    Returns the updated weights dict.
    """
    weights = _load_weights(r)

    if label == "false_positive":
        # Too many false alarms → reduce IsolationForest sensitivity
        weights["isolation_forest"] = _clamp(
            weights["isolation_forest"] - WEIGHT_PENALTY, WEIGHT_MIN, WEIGHT_MAX
        )
    elif label == "true_anomaly":
        # Confirmed anomaly → gently restore weight if it was penalised
        weights["isolation_forest"] = _clamp(
            weights["isolation_forest"] + WEIGHT_REWARD, WEIGHT_MIN, WEIGHT_MAX
        )
    # expected_change: weights unchanged; baseline is reset separately

    _save_weights(r, weights)
    logger.info(f"[Feedback] Weights updated → {weights}")
    return weights


# ─────────────────────────────────────────────────────────────────────────────
# Baseline reset command
# ─────────────────────────────────────────────────────────────────────────────

def _trigger_baseline_reset(r: redis.Redis, agent_id: str) -> None:
    """
    Publish a baseline reset command so the baseline_manager resets the
    rolling window for this agent — acknowledge that the change is expected.
    """
    cmd = json.dumps({"action": "reset_baseline", "agent_id": agent_id})
    r.publish(BASELINE_RESET_CHANNEL, cmd)
    logger.info(f"[Feedback] Baseline reset command published for agent '{agent_id}'.")


# ─────────────────────────────────────────────────────────────────────────────
# DB persistence
# ─────────────────────────────────────────────────────────────────────────────

async def _persist_feedback(fb: FeedbackCreate) -> Optional[int]:
    """Insert feedback label into the DB. Returns inserted row id or None."""
    try:
        row = await fetch_one(
            """
            INSERT INTO feedback_labels
                (anomaly_event_id, agent_id, ts, label, note)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            fb.anomaly_event_id,
            fb.agent_id,
            datetime.now(timezone.utc),
            fb.label,
            fb.note,
        )
        return row["id"] if row else None
    except Exception as exc:
        logger.warning(f"[Feedback] DB persist failed: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def process_feedback(fb: FeedbackCreate) -> dict:
    """
    Main entry point called by the FastAPI /api/feedback endpoint.

    Returns a summary dict suitable for JSON response.
    """
    r = get_sync_client()

    # 1. Persist to DB
    record_id = await _persist_feedback(fb)

    # 2. Adjust model weights
    updated_weights = _adjust_weights(r, fb.label)

    # 3. If expected_change → reset agent baseline
    if fb.label == "expected_change":
        _trigger_baseline_reset(r, fb.agent_id)

    action_taken = {
        "false_positive": "IsolationForest weight reduced. Future sensitivity lowered.",
        "true_anomaly": "Anomaly reinforced. Model confidence increased.",
        "expected_change": "Baseline reset scheduled for agent. Change acknowledged.",
    }[fb.label]

    return {
        "status": "accepted",
        "record_id": record_id,
        "label": fb.label,
        "agent_id": fb.agent_id,
        "action": action_taken,
        "current_weights": updated_weights,
    }


def get_current_weights() -> dict:
    """
    Synchronous helper for the AI inference worker to read ensemble weights.
    Returns the weight dict from Redis (or defaults if none recorded yet).
    """
    r = get_sync_client()
    return _load_weights(r)
