from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import os
import random
import time

import redis.asyncio as redis_async

app = FastAPI()

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    with open("dashboard/static/index.html") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

async def telemetry_generator():
    """Reads real intelligence events from Redis Pub/Sub."""
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    print(f"Connecting Dashboard to Redis at {redis_host}:{redis_port}...")
    r = redis_async.Redis(host=redis_host, port=redis_port, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("anomalies_feed")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield message["data"]   # EventSourceResponse adds "data:" automatically
    except asyncio.CancelledError:
        print("Frontend disconnected.")

@app.get("/api/stream")
async def stream_telemetry():
    """Streams live telemetry via SSE."""
    return EventSourceResponse(telemetry_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
