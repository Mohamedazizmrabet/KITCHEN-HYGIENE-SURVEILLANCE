"""
services/stream_manager.py — OpenCV / Playwright capture + detection + tracking + MJPEG.

Pipeline:
    Video Source (webcam / RTSP / file / browser embed)
        ↓
    OpenCV VideoCapture  ─── fallback ──→  Playwright capture_embedded_player()
        ↓
    Active Detector(s).predict()
        ↓
    PPETracker.update()
        ↓
    Frame Annotation (colour-coded bounding boxes + HUD)
        ↓
    Violation Snapshot Capture (auto-saves frame on violation events)
        ↓
    MJPEG byte generator (consumed by FastAPI StreamingResponse)

Bounding box colour coding:
    Green  → fully compliant person
    Red    → confirmed violation
    Orange → low-confidence detection (conf < LOW_CONF_THRESHOLD)
"""

from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

import cv2
import numpy as np

import config
from detectors.base_detector import BaseDetector, Detection
from tracking.tracker import PPETracker, TrackState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (BGR)
# ---------------------------------------------------------------------------
_GREEN   = (50, 220, 50)    # Compliant person
_RED     = (40, 40, 240)    # Violation confirmed
_ORANGE  = (30, 165, 255)   # Low confidence / uncertain
_GOLD    = (30, 180, 230)   # PPE item detection
_WHITE   = (220, 220, 220)  # Generic label text

_FONT = cv2.FONT_HERSHEY_SIMPLEX

# Confidence below which we draw orange instead of red/green
LOW_CONF_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Violation snapshot
# ---------------------------------------------------------------------------

@dataclass
class ViolationSnapshot:
    snapshot_id: str
    session_id: str
    track_id: int
    timestamp: str          # ISO-8601
    violations: List[str]
    image_b64: str          # base64-encoded JPEG

    def to_dict(self, include_image: bool = True) -> dict:
        d = {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "track_id": self.track_id,
            "timestamp": self.timestamp,
            "violations": self.violations,
        }
        if include_image:
            d["image_b64"] = self.image_b64
        return d


# ---------------------------------------------------------------------------
# Session metrics
# ---------------------------------------------------------------------------

@dataclass
class SessionMetrics:
    fps: float = 0.0
    latency_ms: float = 0.0
    total_detections: int = 0
    active_violations: int = 0
    frame_count: int = 0
    model_name: str = ""

    def to_dict(self) -> dict:
        return {
            "fps": round(self.fps, 1),
            "latency_ms": round(self.latency_ms, 2),
            "total_detections": self.total_detections,
            "active_violations": self.active_violations,
            "frame_count": self.frame_count,
            "model_name": self.model_name,
        }


# ---------------------------------------------------------------------------
# Stream Session
# ---------------------------------------------------------------------------

class StreamSession:
    """Manages a single video stream with detection, tracking, and snapshots.

    Args:
        session_id:  Unique identifier for this stream session.
        source:      Video source — int (webcam), RTSP URL, file path, or embed URL.
        detector:    Loaded BaseDetector instance (or None for passthrough).
        model_name:  Human-readable model name for HUD display.
    """

    def __init__(
        self,
        session_id: str,
        source,
        detector: Optional[BaseDetector],
        model_name: str = "unknown",
    ) -> None:
        self.session_id = session_id
        self.source = source
        self.detector = detector
        self.model_name = model_name

        self.metrics = SessionMetrics(model_name=model_name)
        self.tracker = PPETracker(device=config.DEVICE)

        self._cap: Optional[cv2.VideoCapture] = None
        self._using_playwright = False
        self._playwright_gen = None  # generator from capture_embedded_player()
        self._running = False
        self._current_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None

        # Track states for API polling
        self._track_states: List[dict] = []
        self._track_lock = threading.Lock()

        # Violation snapshots store: snapshot_id → ViolationSnapshot
        self._snapshots: Dict[str, ViolationSnapshot] = {}
        self._snapshot_lock = threading.Lock()
        # Maps track_id -> frozenset of violations (to avoid duplicate snapshots for the exact same violations)
        self._violation_track_ids: dict = {}

        # FPS rolling window
        self._frame_times: deque = deque(maxlen=60)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Open video source and start background capture thread."""
        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name=f"capture-{self.session_id}"
        )
        self._capture_thread.start()
        logger.info(f"[StreamSession:{self.session_id}] Started. Source: {self.source}")

    def stop(self) -> None:
        """Stop capture thread and release resources."""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=5.0)
        if self._cap:
            self._cap.release()
        self._playwright_gen = None
        self.tracker.reset()
        logger.info(f"[StreamSession:{self.session_id}] Stopped.")

    # ------------------------------------------------------------------
    # Public getters (thread-safe)
    # ------------------------------------------------------------------

    def get_track_states(self) -> List[dict]:
        """Return latest track states for API polling."""
        with self._track_lock:
            return list(self._track_states)

    def get_snapshots(self) -> List[dict]:
        """Return all violation snapshots (without image data for list view)."""
        with self._snapshot_lock:
            return [s.to_dict(include_image=False) for s in self._snapshots.values()]

    def get_snapshot(self, snapshot_id: str) -> Optional[ViolationSnapshot]:
        """Return a single snapshot by ID."""
        with self._snapshot_lock:
            return self._snapshots.get(snapshot_id)

    # ------------------------------------------------------------------
    # MJPEG generator
    # ------------------------------------------------------------------

    def mjpeg_frames(self) -> Generator[bytes, None, None]:
        """Yield MJPEG multipart chunks for FastAPI StreamingResponse."""
        boundary = b"--frame\r\n"
        content_type = b"Content-Type: image/jpeg\r\n\r\n"

        while self._running:
            frame = self._get_annotated_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            ok, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.MJPEG_QUALITY]
            )
            if not ok:
                continue

            yield boundary + content_type + jpeg.tobytes() + b"\r\n"
            time.sleep(1.0 / config.STREAM_FPS)

    # ------------------------------------------------------------------
    # Private — capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Background thread: read frames, run detection, update state."""
        # Try to open the source
        self._open_source()

        while self._running:
            frame = self._read_next_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            t_start = time.perf_counter()

            # ---- Detection ----
            detections: List[Detection] = []
            if self.detector and self.detector.is_loaded:
                detections = self.detector.predict(frame)
                
            # ---- Tracking ----
            track_states = self.tracker.update(detections, frame)

            # ---- Metrics ----
            latency = (time.perf_counter() - t_start) * 1000
            self._frame_times.append(time.perf_counter())
            fps = self._compute_fps()

            self.metrics.fps = fps
            self.metrics.latency_ms = latency
            self.metrics.total_detections = len(detections)
            self.metrics.active_violations = sum(
                1 for s in track_states if not s.is_compliant
            )
            self.metrics.frame_count += 1

            # ---- Update track states for API ----
            with self._track_lock:
                self._track_states = [s.to_dict() for s in track_states]

            # ---- Annotation ----
            annotated = self._annotate(frame.copy(), detections, track_states)

            # ---- Violation snapshots ----
            self._check_snapshots(annotated, track_states)

            with self._lock:
                self._current_frame = annotated

    def _open_source(self) -> None:
        """Open video source — OpenCV first, Playwright fallback for embed URLs."""
        from services.stream_utils import is_browser_url, capture_embedded_player, EmbeddedCaptureConfig

        source_str = str(self.source)

        # Check if this is a browser-embed URL
        if isinstance(self.source, str) and is_browser_url(self.source):
            logger.info(
                f"[StreamSession:{self.session_id}] "
                f"Browser embed detected — using Playwright capture."
            )
            cfg = EmbeddedCaptureConfig(
                url=self.source,
                fps=config.STREAM_FPS,
                headless=True,
            )
            self._playwright_gen = capture_embedded_player(cfg)
            self._using_playwright = True
            return

        # Standard OpenCV path
        source = self.source if isinstance(self.source, str) else int(self.source)
        self._cap = cv2.VideoCapture(source)

        if self._cap.isOpened():
            self._using_playwright = False
            logger.info(f"[StreamSession:{self.session_id}] OpenCV capture opened.")
        else:
            logger.warning(
                f"[StreamSession:{self.session_id}] "
                f"OpenCV failed to open '{self.source}'. Checking if Playwright can help..."
            )
            # Try Playwright fallback for any HTTP URL
            if isinstance(self.source, str) and self.source.startswith("http"):
                logger.info(
                    f"[StreamSession:{self.session_id}] "
                    f"Falling back to Playwright screenshot capture."
                )
                cfg = EmbeddedCaptureConfig(url=self.source, fps=5.0, headless=True)
                self._playwright_gen = capture_embedded_player(cfg)
                self._using_playwright = True
            else:
                logger.error(
                    f"[StreamSession:{self.session_id}] "
                    f"Cannot open video source: {self.source}"
                )

    def _read_next_frame(self) -> Optional[np.ndarray]:
        """Read the next frame from either OpenCV or the Playwright generator."""
        if self._using_playwright:
            try:
                return next(self._playwright_gen)
            except StopIteration:
                self._running = False
                return None
            except Exception as exc:
                logger.warning(f"[StreamSession:{self.session_id}] Playwright read error: {exc}")
                return None

        # OpenCV path
        if self._cap is None or not self._cap.isOpened():
            logger.warning(f"[StreamSession:{self.session_id}] Capture lost, retrying…")
            time.sleep(2.0)
            self._open_source()
            return None

        ret, frame = self._cap.read()
        if not ret:
            # For video files loop back; for live streams reconnect
            if isinstance(self.source, str) and not self.source.startswith("rtsp"):
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            else:
                time.sleep(1.0)
                self._open_source()
            return None

        return frame

    def _get_annotated_frame(self) -> Optional[np.ndarray]:
        """Thread-safe access to the latest annotated frame."""
        with self._lock:
            if self._current_frame is None:
                return self._placeholder_frame()
            return self._current_frame.copy()

    # ------------------------------------------------------------------
    # Violation snapshot capture
    # ------------------------------------------------------------------

    def _check_snapshots(
        self, frame: np.ndarray, track_states: List[TrackState]
    ) -> None:
        """Capture a snapshot when a person enters a new violation state."""
        for state in track_states:
            tid = state.track_id
            current_violations = frozenset(state.missing_ppe)
            
            if not state.is_compliant:
                # Take snapshot if this is a brand new violation, or if their violations CHANGED
                # (e.g. they were missing a mask, but now they are missing a mask AND gloves)
                if tid not in self._violation_track_ids or self._violation_track_ids[tid] != current_violations:
                    self._violation_track_ids[tid] = current_violations
                    self._save_snapshot(frame, state)
            elif state.is_compliant and tid in self._violation_track_ids:
                # Person became compliant again — clear them so we can capture next time
                del self._violation_track_ids[tid]

    def _save_snapshot(self, frame: np.ndarray, state: TrackState) -> None:
        """Encode the frame as JPEG and store in the snapshot store."""
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return

        snap = ViolationSnapshot(
            snapshot_id=str(uuid.uuid4()),
            session_id=self.session_id,
            track_id=state.track_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            violations=list(state.missing_ppe),
            image_b64=base64.b64encode(buf.tobytes()).decode("utf-8"),
        )

        with self._snapshot_lock:
            self._snapshots[snap.snapshot_id] = snap

        logger.info(
            f"[StreamSession:{self.session_id}] "
            f"Snapshot saved for Person #{state.track_id} | "
            f"violations={state.missing_ppe}"
        )

    # ------------------------------------------------------------------
    # Annotation
    # ------------------------------------------------------------------

    def _annotate(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        track_states: List[TrackState],
    ) -> np.ndarray:
        """Draw colour-coded bounding boxes, labels, and HUD on the frame."""

        # Draw raw PPE item detections (non-person classes)
        for det in detections:
            if det.class_name.lower() in ("person",):
                continue  # persons drawn via track states
            x1, y1, x2, y2 = [int(v) for v in det.bbox]

            if det.confidence < LOW_CONF_THRESHOLD:
                colour = _ORANGE
            elif det.class_name in config.VIOLATION_CLASSES:
                colour = _RED
            else:
                colour = _GOLD

            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 1)
            label = f"{det.class_name} {det.confidence:.2f}"
            cv2.putText(frame, label, (x1, max(y1 - 5, 12)), _FONT, 0.45, colour, 1)

        # Draw tracked persons with colour-coded boxes
        for state in track_states:
            x1, y1, x2, y2 = [int(v) for v in state.bbox]

            # Determine colour based on compliance + confidence proxy
            if not state.is_compliant:
                colour = _RED
            else:
                colour = _GREEN

            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)

            # Header label
            status_text = "OK" if state.is_compliant else "VIOLATION"
            header = f"Person #{state.track_id}  [{status_text}]"
            # Background pill for readability
            (tw, th), _ = cv2.getTextSize(header, _FONT, 0.52, 2)
            cv2.rectangle(
                frame,
                (x1, max(y1 - th - 10, 0)),
                (x1 + tw + 6, y1),
                colour,
                -1,
            )
            cv2.putText(
                frame, header,
                (x1 + 3, max(y1 - 5, 12)),
                _FONT, 0.52, (0, 0, 0), 2
            )

            # PPE status lines below the box
            y_off = y2 + 16
            for ppe in state.detected_ppe:
                cv2.putText(frame, f"+ {ppe}", (x1, y_off), _FONT, 0.42, _GREEN, 1)
                y_off += 15
            for ppe in state.missing_ppe:
                cv2.putText(frame, f"- {ppe}", (x1, y_off), _FONT, 0.42, _RED, 1)
                y_off += 15

        self._draw_hud(frame)
        return frame

    def _draw_hud(self, frame: np.ndarray) -> None:
        """Draw semi-transparent HUD with live metrics."""
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (270, 115), (15, 15, 20), -1)
        cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

        lines = [
            f"Model: {self.model_name}",
            f"FPS:   {self.metrics.fps:.1f}",
            f"Lat:   {self.metrics.latency_ms:.1f} ms",
            f"Dets:  {self.metrics.total_detections}",
            f"Violations: {self.metrics.active_violations}",
        ]
        for i, line in enumerate(lines):
            colour = (0, 200, 255) if i == 0 else (200, 200, 200)
            cv2.putText(frame, line, (8, 20 + i * 20), _FONT, 0.52, colour, 1)

    @staticmethod
    def _placeholder_frame() -> np.ndarray:
        """Generate a placeholder frame when no video source is available."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (20, 18, 30)
        cv2.putText(
            frame, "Waiting for video source…",
            (60, 225), _FONT, 0.85, (80, 80, 120), 2,
        )
        cv2.putText(
            frame, "Enter a source and press Start",
            (95, 260), _FONT, 0.55, (50, 50, 80), 1,
        )
        return frame

    def _compute_fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        elapsed = self._frame_times[-1] - self._frame_times[0]
        return (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0


# ---------------------------------------------------------------------------
# Global snapshot store (accessible cross-session for the download endpoint)
# ---------------------------------------------------------------------------

# Maps snapshot_id → ViolationSnapshot across all sessions
_global_snapshot_store: Dict[str, ViolationSnapshot] = {}
_global_snapshot_lock = threading.Lock()


def register_snapshot(snap: ViolationSnapshot) -> None:
    """Register a snapshot in the global store."""
    with _global_snapshot_lock:
        _global_snapshot_store[snap.snapshot_id] = snap


def get_global_snapshot(snapshot_id: str) -> Optional[ViolationSnapshot]:
    """Retrieve a snapshot by ID from the global store."""
    with _global_snapshot_lock:
        return _global_snapshot_store.get(snapshot_id)


# ---------------------------------------------------------------------------
# Stream Manager (session registry)
# ---------------------------------------------------------------------------

class StreamManager:
    """Global registry of active StreamSession objects."""

    def __init__(self) -> None:
        self._sessions: Dict[str, StreamSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        session_id: str,
        source,
        detector: Optional[BaseDetector],
        model_name: str = "unknown",
    ) -> StreamSession:
        """Create and start a new stream session."""
        session = StreamSession(
            session_id=session_id,
            source=source,
            detector=detector,
            model_name=model_name,
        )
        session.start()
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def stop_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.stop()
            return True
        return False

    def list_sessions(self) -> List[str]:
        with self._lock:
            return list(self._sessions.keys())

    def stop_all(self) -> None:
        """Stop all active sessions (called on service shutdown)."""
        for sid in self.list_sessions():
            self.stop_session(sid)
