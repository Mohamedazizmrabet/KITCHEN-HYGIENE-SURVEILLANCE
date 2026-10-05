"""
app.py — FastAPI application entry point.

Creates the FastAPI app, configures CORS, mounts all routers,
and registers startup/shutdown lifecycle hooks.

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.routes import router, init_detectors, _stream_manager

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOGS_DIR / "inference.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("=" * 60)
    logger.info("  Kitchen Hygiene Surveillance — Inference Service")
    logger.info(f"  Device: {config.DEVICE}")
    logger.info(f"  Default model: {config.DEFAULT_MODEL}")
    logger.info(f"  YOLO weights:  {config.YOLO_MODEL_PATH}")
    logger.info(f"  RTDETR weights:{config.RTDETR_MODEL_PATH}")
    logger.info("=" * 60)

    # Initialise detectors (non-blocking — missing weights are warned, not crashed)
    init_detectors()

    yield  # Application runs here

    # Graceful shutdown
    logger.info("Shutting down — stopping all active sessions…")
    _stream_manager.stop_all()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Kitchen Hygiene Surveillance — Inference Service",
    description=(
        "Real-time PPE monitoring prototype using separate YOLO and RT-DETR detectors. "
        "Provides MJPEG streaming, BoT-SORT tracking, and model benchmarking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow React frontend and Laravel to connect
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React Vite dev server
        "http://localhost:5173",   # Vite alternative port
        "http://localhost:8000",   # Laravel
        "*",                       # Relaxed for development — restrict in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------

app.include_router(router, tags=["Inference"])


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "service": "Kitchen Hygiene Surveillance — Inference Service",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ---------------------------------------------------------------------------
# Direct run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower(),
    )
