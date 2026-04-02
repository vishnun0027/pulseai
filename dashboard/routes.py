"""
dashboard/routes.py
FastAPI APIRouter with all REST endpoints for the dashboard.

Endpoints:
  GET  /api/anomalies        — paginated anomaly events with filters
  GET  /api/agents           — per-agent summary stats
  GET  /api/anomalies/{id}   — single anomaly event with SHAP explanation
  POST /api/feedback         — submit a feedback label
  GET  /api/stream           — SSE real-time stream (moved from main.py)
  GET  /api/health           — health check
"""

import asyncio
import csv
import json
import logging
from io import StringIO
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from dashboard.auth import AuthUser, get_authenticated_user
from feedback.handler import process_feedback
from storage.db import fetch_all, fetch_one
from storage.models import FeedbackCreate

logger = logging.getLogger(__name__)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# SSE live stream
# ─────────────────────────────────────────────────────────────────────────────

from dashboard.broadcast import broadcaster

async def _telemetry_generator():
    """Subscribes to the shared broadcaster and yields SSE frames."""
    try:
        # Use the shared broadcaster instead of many individual Redis connections
        async for msg in broadcaster.subscribe():
            yield msg
    except asyncio.CancelledError:
        logger.info("[SSE] Frontend disconnected.")


@router.get("/api/stream", tags=["stream"])
async def stream_telemetry(current_user: AuthUser = Depends(get_authenticated_user)):
    """Server-Sent Events endpoint — real-time scored telemetry."""
    return EventSourceResponse(_telemetry_generator())


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly events
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/anomalies", tags=["anomalies"])
async def list_anomalies(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    only_anomalies: bool = Query(False, description="Return only anomalous events"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    from_ts: Optional[datetime] = Query(None, description="Start timestamp (ISO 8601)"),
    to_ts: Optional[datetime] = Query(None, description="End timestamp (ISO 8601)"),
    current_user: AuthUser = Depends(get_authenticated_user),
):
    """
    Return paginated anomaly events with optional filters.
    Reads from TimescaleDB; falls back to empty list if DB is unavailable.
    """
    try:
        conditions = []
        params = []
        idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${idx}")
            params.append(agent_id)
            idx += 1
        if only_anomalies:
            conditions.append(f"is_anomaly = TRUE")
        if from_ts:
            conditions.append(f"ts >= ${idx}")
            params.append(from_ts)
            idx += 1
        if to_ts:
            conditions.append(f"ts <= ${idx}")
            params.append(to_ts)
            idx += 1

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Count total
        count_row = await fetch_one(
            f"SELECT COUNT(*) AS total FROM anomaly_events {where_clause}", *params
        )
        total = count_row["total"] if count_row else 0

        # Fetch page
        params_page = params + [limit, offset]
        rows = await fetch_all(
            f"""
            SELECT id, agent_id, ts, cpu_usage, used_memory_gb,
                   anomaly_score, is_anomaly, drift_detected, explanation
            FROM anomaly_events
            {where_clause}
            ORDER BY ts DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params_page,
        )

        items = [
            {
                "id": r["id"],
                "agent_id": r["agent_id"],
                "ts": r["ts"].isoformat(),
                "cpu_usage": r["cpu_usage"],
                "used_memory_gb": r["used_memory_gb"],
                "anomaly_score": r["anomaly_score"],
                "is_anomaly": r["is_anomaly"],
                "drift_detected": r["drift_detected"],
                "explanation": r["explanation"] or {},
            }
            for r in rows
        ]
        return JSONResponse({"total": total, "items": items})

    except Exception as exc:
        logger.warning(f"[API] /api/anomalies DB error: {exc}")
        return JSONResponse({"total": 0, "items": [], "error": "DB unavailable"})


@router.get("/api/anomalies/{event_id}", tags=["anomalies"])
async def get_anomaly(
    event_id: int,
    current_user: AuthUser = Depends(get_authenticated_user),
):
    """Return a single anomaly event including its SHAP explanation."""
    try:
        row = await fetch_one(
            """
            SELECT id, agent_id, ts, cpu_usage, used_memory_gb,
                   anomaly_score, is_anomaly, drift_detected, explanation
            FROM anomaly_events WHERE id = $1
            """,
            event_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Anomaly event not found")
        return {
            "id": row["id"],
            "agent_id": row["agent_id"],
            "ts": row["ts"].isoformat(),
            "cpu_usage": row["cpu_usage"],
            "used_memory_gb": row["used_memory_gb"],
            "anomaly_score": row["anomaly_score"],
            "is_anomaly": row["is_anomaly"],
            "drift_detected": row["drift_detected"],
            "explanation": row["explanation"] or {},
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[API] /api/anomalies/{event_id} DB error: {exc}")
        raise HTTPException(status_code=503, detail="DB unavailable")


# ─────────────────────────────────────────────────────────────────────────────
# Agent summaries
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/agents", tags=["agents"])
async def list_agents(current_user: AuthUser = Depends(get_authenticated_user)):
    """Per-agent summary: total events, anomaly count, anomaly rate, last seen."""
    try:
        rows = await fetch_all(
            """
            SELECT
                agent_id,
                COUNT(*)                                    AS total_events,
                SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) AS anomaly_count,
                MAX(ts)                                     AS last_seen
            FROM anomaly_events
            GROUP BY agent_id
            ORDER BY last_seen DESC
            """
        )
        return [
            {
                "agent_id": r["agent_id"],
                "total_events": r["total_events"],
                "anomaly_count": r["anomaly_count"],
                "anomaly_rate": round(r["anomaly_count"] / r["total_events"], 3)
                if r["total_events"] > 0
                else 0.0,
                "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning(f"[API] /api/agents DB error: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Feedback
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/feedback", tags=["feedback"])
async def submit_feedback(
    fb: FeedbackCreate,
    current_user: AuthUser = Depends(get_authenticated_user),
):
    """
    Submit a feedback label on an anomaly event.

    Labels: false_positive | true_anomaly | expected_change
    """
    result = await process_feedback(fb)
    return JSONResponse(content=result, status_code=201)


@router.get("/api/reports/export", tags=["reports"])
async def export_report_csv(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    only_anomalies: bool = Query(False, description="Return only anomalous events"),
    from_ts: Optional[datetime] = Query(None, description="Start timestamp (ISO 8601)"),
    to_ts: Optional[datetime] = Query(None, description="End timestamp (ISO 8601)"),
    current_user: AuthUser = Depends(get_authenticated_user),
):
    conditions = []
    params = []
    idx = 1

    if agent_id:
        conditions.append(f"agent_id = ${idx}")
        params.append(agent_id)
        idx += 1
    if only_anomalies:
        conditions.append("is_anomaly = TRUE")
    if from_ts:
        conditions.append(f"ts >= ${idx}")
        params.append(from_ts)
        idx += 1
    if to_ts:
        conditions.append(f"ts <= ${idx}")
        params.append(to_ts)
        idx += 1

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await fetch_all(
        f"""
        SELECT id, agent_id, ts, cpu_usage, used_memory_gb,
               anomaly_score, is_anomaly, drift_detected, explanation
        FROM anomaly_events
        {where_clause}
        ORDER BY ts DESC
        """,
        *params,
    )

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "agent_id",
            "timestamp",
            "cpu_usage",
            "used_memory_gb",
            "anomaly_score",
            "is_anomaly",
            "drift_detected",
            "explanation_json",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["agent_id"],
                row["ts"].isoformat() if row["ts"] else "",
                row["cpu_usage"],
                row["used_memory_gb"],
                row["anomaly_score"],
                row["is_anomaly"],
                row["drift_detected"],
                json.dumps(row["explanation"] or {}),
            ]
        )

    filename = f"pulseai-report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "anomaly-dashboard"}
