"""
dashboard/main.py
PulseAI — FastAPI application entry point.
Mounts the APIRouter from dashboard/routes.py and manages DB pool lifecycle.
"""

import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from dashboard.routes import router
from storage.db import init_pool, close_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle — init and close DB pool."""
    try:
        await init_pool()
        from storage.db import run_migrations
        await run_migrations()
        logger.info("[Dashboard] DB pool and migrations ready.")
    except Exception as exc:
        logger.warning(f"[Dashboard] DB unavailable at startup: {exc}")
    yield
    await close_pool()


app = FastAPI(
    title="PulseAI — Anomaly Intelligence API",
    description="PulseAI: Real-time AI-powered system behavior anomaly monitoring with SHAP explainability and self-learning feedback.",
    version="2.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Include all REST + SSE routes
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    with open("dashboard/static/index.html") as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.main:app", host="0.0.0.0", port=8000, reload=False)
