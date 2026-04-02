"""
storage/cache.py
Redis helper wrappers — get/set with TTL, pub/sub utilities,
and typed accessors used across the Python services.
"""

import json
import os
import logging
from typing import Any, Callable, Optional

import redis.asyncio as aioredis
import redis as syncredis

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Connection factories
# ─────────────────────────────────────────────────────────────────────────────

def _redis_kwargs() -> dict:
    return {
        "host": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", "6379")),
        "decode_responses": True,
    }


def get_sync_client() -> syncredis.Redis:
    """Return a synchronous Redis client (used by AI consumer)."""
    return syncredis.Redis(**_redis_kwargs())


async def get_async_client() -> aioredis.Redis:
    """Return an async Redis client (used by FastAPI dashboard)."""
    return aioredis.Redis(**_redis_kwargs())


# ─────────────────────────────────────────────────────────────────────────────
# Key/Value helpers (async)
# ─────────────────────────────────────────────────────────────────────────────

async def cache_set(client: aioredis.Redis, key: str, value: Any, ttl_s: int = 300) -> None:
    """Serialize value to JSON and store with TTL."""
    payload = json.dumps(value)
    if ttl_s and ttl_s > 0:
        await client.setex(key, ttl_s, payload)
    else:
        await client.set(key, payload)


async def cache_get(client: aioredis.Redis, key: str) -> Optional[Any]:
    """Retrieve and deserialize a cached value. Returns None on miss."""
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_delete(client: aioredis.Redis, key: str) -> None:
    await client.delete(key)


# ─────────────────────────────────────────────────────────────────────────────
# Key/Value helpers (sync)
# ─────────────────────────────────────────────────────────────────────────────

def cache_set_sync(client: syncredis.Redis, key: str, value: Any, ttl_s: int = 300) -> None:
    payload = json.dumps(value)
    if ttl_s and ttl_s > 0:
        client.setex(key, ttl_s, payload)
    else:
        client.set(key, payload)


def cache_get_sync(client: syncredis.Redis, key: str) -> Optional[Any]:
    raw = client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Stream helpers (sync — used by AI consumer)
# ─────────────────────────────────────────────────────────────────────────────

def stream_publish(client: syncredis.Redis, channel: str, payload: dict) -> None:
    """Publish a JSON payload to a Redis Pub/Sub channel."""
    client.publish(channel, json.dumps(payload))


def stream_xadd(client: syncredis.Redis, stream: str, payload: dict) -> str:
    """Add a JSON payload to a Redis Stream. Returns the message ID."""
    return client.xadd(stream, {"payload": json.dumps(payload)})


# ─────────────────────────────────────────────────────────────────────────────
# Common cache key namespaces
# ─────────────────────────────────────────────────────────────────────────────

class CacheKeys:
    """Centralised key templates to avoid typos across services."""

    @staticmethod
    def agent_summary(agent_id: str) -> str:
        return f"agent_summary:{agent_id}"

    @staticmethod
    def recent_anomalies(agent_id: str) -> str:
        return f"recent_anomalies:{agent_id}"

    @staticmethod
    def feedback_weights() -> str:
        return "feedback:ensemble_weights"

    @staticmethod
    def dashboard_stats() -> str:
        return "dashboard:stats"
