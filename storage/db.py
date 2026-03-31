"""
storage/db.py
Async PostgreSQL / TimescaleDB connection pool manager.

Usage:
    from storage.db import get_pool, close_pool, fetch_all, execute

The pool is initialized once at app startup and shared by all workers.
"""

import asyncpg
import os
import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _dsn() -> str:
    """Build DSN from environment variables with sane defaults."""
    host = os.environ.get("DB_HOST", "timescaledb")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "anomaly")
    password = os.environ.get("DB_PASSWORD", "anomaly")
    database = os.environ.get("DB_NAME", "anomalydb")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def init_pool(min_size: int = 2, max_size: int = 10) -> None:
    """
    Create and store the global connection pool.
    Call once at application startup.
    """
    global _pool
    if _pool is not None:
        return
    dsn = _dsn()
    logger.info(f"[DB] Connecting to TimescaleDB at {dsn.split('@')[-1]}")
    _pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
    logger.info("[DB] Connection pool established.")


async def close_pool() -> None:
    """Gracefully close the connection pool on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] Connection pool closed.")


def get_pool() -> asyncpg.Pool:
    """Return the active pool. Raises if init_pool() was not called."""
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call storage.db.init_pool() first.")
    return _pool


async def execute(query: str, *args: Any) -> str:
    """Execute a write query (INSERT/UPDATE/DELETE). Returns status string."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch_all(query: str, *args: Any) -> List[asyncpg.Record]:
    """Execute a SELECT and return all rows."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetch_one(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Execute a SELECT and return the first row or None."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def run_migrations() -> None:
    """
    Create all required tables if they do not exist.
    TimescaleDB hypertables are created for time-series tables.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # ── Telemetry snapshots (raw agent data) ─────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                agent_id        TEXT        NOT NULL,
                ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                cpu_usage       DOUBLE PRECISION,
                used_memory_gb  DOUBLE PRECISION,
                load_avg_1m     DOUBLE PRECISION,
                gpu_usage       DOUBLE PRECISION,
                env_type        TEXT,
                gap_type        TEXT
            );
        """)
        # Convert to hypertable (idempotent via if_not_exists)
        await conn.execute("""
            SELECT create_hypertable(
                'telemetry_snapshots', 'ts',
                if_not_exists => TRUE,
                migrate_data  => TRUE
            );
        """)

        # ── Anomaly events ────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_events (
                id              BIGSERIAL,
                agent_id        TEXT        NOT NULL,
                ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                cpu_usage       DOUBLE PRECISION,
                used_memory_gb  DOUBLE PRECISION,
                anomaly_score   DOUBLE PRECISION,
                is_anomaly      BOOLEAN,
                drift_detected  BOOLEAN,
                explanation     JSONB,
                UNIQUE (agent_id, ts)
            );
        """)
        await conn.execute("""
            SELECT create_hypertable(
                'anomaly_events', 'ts',
                if_not_exists => TRUE,
                migrate_data  => TRUE
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_agent_ts
                ON anomaly_events (agent_id, ts DESC);
        """)

        # ── Feedback labels ───────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_labels (
                id              BIGSERIAL   PRIMARY KEY,
                anomaly_event_id BIGINT,
                agent_id        TEXT        NOT NULL,
                ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                label           TEXT        NOT NULL CHECK (label IN ('false_positive','true_anomaly','expected_change')),
                note            TEXT
            );
        """)

        logger.info("[DB] Migrations complete — all tables ready.")
