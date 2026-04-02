import asyncio
import json
import logging
import os
from typing import Optional, Set

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

class RedisBroadcast:
    """
    Manages a single Redis Pub/Sub subscription and broadcasts received
    messages to all connected SSE clients via internal memory queues.
    
    This prevents 'Redis connection bloat' by ensuring only ONE 
    connection is used for the entire application.
    """
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()
        self.redis_host = os.environ.get("REDIS_HOST", "localhost")
        self.redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        self.listener_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background Redis listener."""
        self.listener_task = asyncio.create_task(self._listen())
        logger.info("[Broadcast] Shared Redis listener started.")

    async def stop(self):
        """Clean up the listener and Redis connection."""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        logger.info("[Broadcast] Shared Redis listener stopped.")

    async def _listen(self):
        """Infinite loop reading from Redis and pushing to subscriber queues."""
        r = aioredis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("anomalies_feed")
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    # Distribute to all active memory queues
                    if self.subscribers:
                        for q in self.subscribers:
                            await q.put(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[Broadcast] Redis listener error: {e}")
        finally:
            await pubsub.unsubscribe("anomalies_feed")
            await r.aclose()

    async def subscribe(self):
        """
        Create a new memory queue for a client and yield messages.
        Usage: 
            async for msg in broadcast.subscribe():
                yield msg
        """
        q = asyncio.Queue()
        self.subscribers.add(q)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            self.subscribers.remove(q)

# Global singleton
broadcaster = RedisBroadcast()
