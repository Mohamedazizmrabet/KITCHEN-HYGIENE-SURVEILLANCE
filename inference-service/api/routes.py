"""
api/routes.py — All FastAPI route handlers.

Endpoints:
    GET  /health                              → service liveness check
    POST /session/start                       → create + start a new stream session
    POST /session/stop                        → stop a running session
    GET  /stream/{id}                         → MJPEG stream for a session
    GET  /session/{id}/tracks                 → live track states for a session
    GET  /session/{id}/snapshots              → list violation snapshots (no image)
    GET  /snapshot/{snapshot_id}/download     → download single snapshot as JPEG
    POST /model/select                        → switch active model
    GET  /metrics                             → current performance metrics
    POST /benchmark/start                     → start benchmark (compare both models)
    POST /benchmark/stop                      → stop benchmark
    GET  /benchmark/stream                    → MJPEG stream for benchmark view
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

import config
from config import ModelMode
from detectors import YOLODetector, RTDETRDetector
from services.stream_manager import StreamManager, get_global_snapshot
from services.benchmark import BenchmarkService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Application state (shared across requests)
# ---------------------------------------------------------------------------

_yolo_detector: YOLODetector | None = None
_rtdetr_detector: RTDETRDetector | None = None
_stream_manager = StreamManager()
_benchmark_service: BenchmarkService | None = None
_active_model: str = config.DEFAULT_MODEL

# Which PPE classes are currently being tracked (can be toggled by user)
_active_ppe_compliance: set = set(config.COMPLIANCE_CLASSES)
_active_ppe_violations: set = set(config.VIOLATION_CLASSES)

# ---------------------------------------------------------------------------
# Detector initialisation (called at startup)
# ---------------------------------------------------------------------------

def init_detectors() -> None:
    """Attempt to load both detectors. Failures are logged, not raised."""
    global _yolo_detector, _rtdetr_detector

    _yolo_detector = YOLODetector(
        model_path=config.YOLO_MODEL_PATH,
        device=config.DEVICE,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
    )
    _yolo_detector.safe_load()

    _rtdetr_detector = RTDETRDetector(
        model_path=config.RTDETR_MODEL_PATH,
        device=config.DEVICE,
        confidence_threshold=config.CONFIDENCE_THRESHOLD,
    )
    _rtdetr_detector.safe_load()


def _get_active_detector(model: str | None = None):
    """Return the detector for the selected model mode."""
    selected_model = model or _active_model
    if selected_model == ModelMode.YOLO:
        return _yolo_detector, "YOLO"
    elif selected_model == ModelMode.RTDETR:
        return _rtdetr_detector, "RT-DETR"
    return None, "none"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SessionStartRequest(BaseModel):
    source: str = Field(default="0", description="Video source: '0' for webcam, RTSP URL, embed URL, or file path")
    model: str = Field(default="", description="Override model for this session. Leave empty to use active model.")

class SessionStartResponse(BaseModel):
    session_id: str
    source: str
    model: str
    stream_url: str

class SessionStopRequest(BaseModel):
    session_id: str

class ModelSelectRequest(BaseModel):
    model: str = Field(description="YOLO | RTDETR | BOTH")

class BenchmarkStartRequest(BaseModel):
    source: str = Field(default="0")

class PPEConfigRequest(BaseModel):
    compliance: list = Field(description="List of compliance class names to track")
    violations: list = Field(description="List of violation class names to track")


# ---------------------------------------------------------------------------
# Routes — PPE Config
# ---------------------------------------------------------------------------

@router.get("/config/ppe")
async def get_ppe_config() -> dict:
    """Return the list of all available PPE classes and which are currently active."""
    all_ppe = {
        "gloves": "no_gloves",
        "mask": "no_mask",
        "hairnet": "no_hairnet",
    }
    return {
        "available": list(all_ppe.keys()),
        "active_compliance": list(_active_ppe_compliance),
        "active_violations": list(_active_ppe_violations),
    }


@router.post("/config/ppe")
async def set_ppe_config(req: PPEConfigRequest) -> dict:
    """Update which PPE items are actively tracked. Affects all new sessions."""
    global _active_ppe_compliance, _active_ppe_violations
    _active_ppe_compliance = set(req.compliance)
    _active_ppe_violations = set(req.violations)
    # Propagate to config so tracker.py picks them up dynamically
    config.COMPLIANCE_CLASSES = _active_ppe_compliance
    config.VIOLATION_CLASSES = _active_ppe_violations
    logger.info(f"[API] PPE config updated: compliance={req.compliance}, violations={req.violations}")
    return {
        "status": "ok",
        "active_compliance": list(_active_ppe_compliance),
        "active_violations": list(_active_ppe_violations),
    }


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health() -> dict:
    """Liveness check. Returns service status and model states."""
    return {
        "status": "ok",
        "device": config.DEVICE,
        "active_model": _active_model,
        "yolo_loaded": _yolo_detector.is_loaded if _yolo_detector else False,
        "rtdetr_loaded": _rtdetr_detector.is_loaded if _rtdetr_detector else False,
        "rt_loaded": _rtdetr_detector.is_loaded if _rtdetr_detector else False,
        "active_sessions": _stream_manager.list_sessions(),
    }


# ---------------------------------------------------------------------------
# Routes — Session
# ---------------------------------------------------------------------------

@router.post("/session/start", response_model=SessionStartResponse)
async def session_start(req: SessionStartRequest) -> SessionStartResponse:
    """Create and start a new inference session."""
    session_id = str(uuid.uuid4())

    model_override = req.model.upper() if req.model else _active_model
    if model_override == ModelMode.BOTH:
        raise HTTPException(
            status_code=400,
            detail="Use /benchmark/start for dual-model comparison mode."
        )

    detector, model_name = _get_active_detector(model_override)
    if detector is None or not detector.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=f"The {model_name} model is not loaded. Check its weights and inference logs.",
        )

    # Convert source string to int if it's a webcam index
    source = int(req.source) if req.source.isdigit() else req.source

    _stream_manager.create_session(
        session_id=session_id,
        source=source,
        detector=detector,
        model_name=model_name,
    )

    stream_url = f"http://localhost:{config.PORT}/stream/{session_id}"
    logger.info(f"[API] Session started: {session_id} | model={model_name} | source={req.source}")

    return SessionStartResponse(
        session_id=session_id,
        source=req.source,
        model=model_name,
        stream_url=stream_url,
    )


@router.post("/session/stop")
async def session_stop(req: SessionStopRequest) -> dict:
    """Stop a running inference session."""
    stopped = _stream_manager.stop_session(req.session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail=f"Session '{req.session_id}' not found.")
    logger.info(f"[API] Session stopped: {req.session_id}")
    return {"status": "stopped", "session_id": req.session_id}


@router.get("/stream/{session_id}")
async def stream(session_id: str) -> StreamingResponse:
    """Serve MJPEG stream for a given session."""
    session = _stream_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    return StreamingResponse(
        session.mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/session/{session_id}/tracks")
async def session_tracks(session_id: str) -> dict:
    """Return live track states (person IDs, PPE status) for a session."""
    session = _stream_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"session_id": session_id, "tracks": session.get_track_states()}


@router.get("/session/{session_id}/snapshots")
async def session_snapshots(session_id: str) -> dict:
    """Return list of violation snapshots for a session (metadata only, no image data)."""
    session = _stream_manager.get_session(session_id)
    if session is None:
        # Session may have stopped — return empty
        return {"session_id": session_id, "snapshots": []}
    snapshots = session.get_snapshots()
    # Also register them globally for download endpoint
    for snap_meta in snapshots:
        snap_obj = session.get_snapshot(snap_meta["snapshot_id"])
        if snap_obj:
            from services.stream_manager import register_snapshot
            register_snapshot(snap_obj)
    return {"session_id": session_id, "snapshots": snapshots}


@router.get("/session/{session_id}/snapshots/full")
async def session_snapshots_full(session_id: str) -> dict:
    """Return violation snapshots including base64 image data."""
    session = _stream_manager.get_session(session_id)
    if session is None:
        return {"session_id": session_id, "snapshots": []}
    with session._snapshot_lock:
        snaps = [s.to_dict(include_image=True) for s in session._snapshots.values()]
    # Register all in global store
    for snap_meta in snaps:
        snap_obj = session.get_snapshot(snap_meta["snapshot_id"])
        if snap_obj:
            from services.stream_manager import register_snapshot
            register_snapshot(snap_obj)
    return {"session_id": session_id, "snapshots": snaps}


@router.get("/snapshot/{snapshot_id}/download")
async def snapshot_download(snapshot_id: str) -> Response:
    """Download a single violation snapshot as a JPEG file."""
    import base64
    snap = get_global_snapshot(snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found.")

    image_bytes = base64.b64decode(snap.image_b64)
    filename = f"violation_person{snap.track_id}_{snap.timestamp[:19].replace(':', '-')}.jpg"

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Routes — Model
# ---------------------------------------------------------------------------

@router.post("/model/select")
async def model_select(req: ModelSelectRequest) -> dict:
    """Switch the active inference model."""
    global _active_model

    model = req.model.upper()
    # Accept "RT" as alias for RTDETR
    if model == "RT":
        model = ModelMode.RTDETR

    valid = {ModelMode.YOLO, ModelMode.RTDETR, ModelMode.BOTH}
    if model not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{req.model}'. Valid options: YOLO, RT, BOTH"
        )

    _active_model = model
    logger.info(f"[API] Active model switched to: {_active_model}")
    return {"status": "ok", "active_model": _active_model}


# ---------------------------------------------------------------------------
# Routes — Metrics
# ---------------------------------------------------------------------------

@router.get("/metrics")
async def metrics() -> dict:
    """Return live performance metrics for all active sessions."""
    session_metrics = {}
    for sid in _stream_manager.list_sessions():
        session = _stream_manager.get_session(sid)
        if session:
            session_metrics[sid] = session.metrics.to_dict()

    benchmark_metrics = _benchmark_service.get_metrics() if _benchmark_service else None

    return {
        "active_model": _active_model,
        "sessions": session_metrics,
        "benchmark": benchmark_metrics,
    }


# ---------------------------------------------------------------------------
# Routes — Benchmark
# ---------------------------------------------------------------------------

@router.post("/benchmark/start")
async def benchmark_start(req: BenchmarkStartRequest) -> dict:
    """Start dual-model benchmark comparison."""
    global _benchmark_service

    if _benchmark_service and _benchmark_service._running:
        return {"status": "already_running"}

    source = int(req.source) if req.source.isdigit() else req.source
    _benchmark_service = BenchmarkService(
        yolo_detector=_yolo_detector,
        rtdetr_detector=_rtdetr_detector,
    )
    try:
        _benchmark_service.start(video_source=source)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"status": "benchmark_started", "source": req.source}


@router.post("/benchmark/stop")
async def benchmark_stop() -> dict:
    """Stop the running benchmark."""
    global _benchmark_service
    if _benchmark_service:
        _benchmark_service.stop()
        _benchmark_service = None
    return {"status": "benchmark_stopped", "csv": str(config.BENCHMARK_CSV_PATH)}


@router.get("/benchmark/stream")
async def benchmark_stream() -> StreamingResponse:
    """Serve the live benchmark comparison MJPEG stream."""
    if _benchmark_service is None or not _benchmark_service._running:
        raise HTTPException(status_code=404, detail="No active benchmark. Call /benchmark/start first.")

    return StreamingResponse(
        _benchmark_service.get_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
