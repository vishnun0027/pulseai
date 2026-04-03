"""
storage/models.py
Pydantic models (schemas) mirroring the database tables.
Used for API validation and clean data passing between layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry Snapshot
# ─────────────────────────────────────────────────────────────────────────────


class TelemetrySnapshot(BaseModel):
    """One raw metric reading received from a Rust agent."""

    agent_id: str
    ts: datetime
    cpu_usage: float
    used_memory_gb: float
    load_avg_1m: Optional[float] = None
    gpu_usage: Optional[float] = None
    env_type: Optional[str] = None
    gap_type: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Event
# ─────────────────────────────────────────────────────────────────────────────


class AnomalyEvent(BaseModel):
    """Record of a scored inference result from the AI pipeline."""

    id: Optional[int] = None
    agent_id: str
    ts: datetime
    cpu_usage: float
    used_memory_gb: float
    anomaly_score: float
    is_anomaly: bool
    drift_detected: bool
    explanation: Dict[str, Any] = Field(default_factory=dict)


class AnomalyEventCreate(BaseModel):
    """Schema used when persisting a new anomaly event."""

    agent_id: str
    ts: datetime
    cpu_usage: float
    used_memory_gb: float
    anomaly_score: float
    is_anomaly: bool
    drift_detected: bool
    explanation: Dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Feedback Label
# ─────────────────────────────────────────────────────────────────────────────

FeedbackLabel = Literal["false_positive", "true_anomaly", "expected_change"]


class FeedbackCreate(BaseModel):
    """Feedback submitted by a user on an anomaly event."""

    anomaly_event_id: Optional[int] = None
    agent_id: str
    label: FeedbackLabel
    note: Optional[str] = None


class FeedbackRecord(FeedbackCreate):
    """Feedback record returned from DB (includes id and ts)."""

    id: int
    ts: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Query Filters
# ─────────────────────────────────────────────────────────────────────────────


class AnomalyQueryParams(BaseModel):
    """Parameters for filtering the anomaly events API."""

    agent_id: Optional[str] = None
    only_anomalies: bool = False
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    from_ts: Optional[datetime] = None
    to_ts: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# API Responses
# ─────────────────────────────────────────────────────────────────────────────


class AnomalyListResponse(BaseModel):
    total: int
    items: List[AnomalyEvent]


class AgentSummary(BaseModel):
    agent_id: str
    total_events: int
    anomaly_count: int
    last_seen: Optional[datetime]
    anomaly_rate: float  # 0.0–1.0
