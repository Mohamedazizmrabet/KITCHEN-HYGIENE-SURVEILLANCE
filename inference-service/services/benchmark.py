"""
services/benchmark.py — Dual-model benchmarking service.

Runs YOLO and RT-DETR on the same frames simultaneously.
Measures and compares:
  - FPS
  - inference latency (ms)
  - number of detections
  - GPU memory usage (if CUDA available)

Results are written to logs/benchmark.csv and served via /metrics.
Annotated frames include a side-by-side HUD for live visual comparison.
"""

from __future__ import annotations

import csv
import logging
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config
from detectors.base_detector import BaseDetector, Detection

logger = logging.getLogger(__name__)

_FONT = cv2.FONT_HERSHEY_SIMPLEX


# ---------------------------------------------------------------------------
# Model benchmark record
# ---------------------------------------------------------------------------

@dataclass
class ModelBenchmark:
    """Rolling performance metrics for a single model."""
    model_name: str
    fps_window: deque = field(default_factory=lambda: deque(maxlen=60))
    latency_window: deque = field(default_factory=lambda: deque(maxlen=60))
    detection_window: deque = field(default_factory=lambda: deque(maxlen=60))
    frame_count: int = 0

    @property
    def fps(self) -> float:
        if len(self.fps_window) < 2:
            return 0.0
        elapsed = self.fps_window[-1] - self.fps_window[0]
        return (len(self.fps_window) - 1) / elapsed if elapsed > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return float(np.mean(self.latency_window)) if self.latency_window else 0.0

    @property
    def avg_detections(self) -> float:
        return float(np.mean(self.detection_window)) if self.detection_window else 0.0

    def record(self, latency_ms: float, num_detections: int) -> None:
        self.fps_window.append(time.perf_counter())
        self.latency_window.append(latency_ms)
        self.detection_window.append(num_detections)
        self.frame_count += 1

    def to_dict(self) -> dict:
        return {
            "model": self.model_name,
            "fps": round(self.fps, 1),
            "latency_ms": round(self.avg_latency_ms, 2),
            "avg_detections": round(self.avg_detections, 2),
            "frame_count": self.frame_count,
        }


# ---------------------------------------------------------------------------
# Benchmark Service
# ---------------------------------------------------------------------------

class BenchmarkService:
    """Runs both models on the same frames and records performance data.

    Usage:
        svc = BenchmarkService(yolo_detector, rtdetr_detector)
        svc.start(video_source=0)
        # Later:
        frame = svc.get_latest_frame()
        metrics = svc.get_metrics()
        svc.stop()
    """

    def __init__(
        self,
        yolo_detector: Optional[BaseDetector],
        rtdetr_detector: Optional[BaseDetector],
    ) -> None:
        self._yolo = yolo_detector
        self._rtdetr = rtdetr_detector

        self._yolo_bench = ModelBenchmark(model_name="YOLO11")
        self._rtdetr_bench = ModelBenchmark(model_name="RT-DETR-L")

        self._running = False
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        # Prepare CSV writer
        self._csv_path = config.BENCHMARK_CSV_PATH
        self._csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._csv_file = None
        self._csv_writer = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, video_source=0) -> None:
        """Open video source and begin benchmarking loop."""
        self._cap = cv2.VideoCapture(
            video_source if isinstance(video_source, str) else int(video_source)
        )
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video source: {video_source}")

        self._open_csv()
        self._running = True
        self._thread = threading.Thread(
            target=self._benchmark_loop, daemon=True, name="benchmark"
        )
        self._thread.start()
        logger.info("[BenchmarkService] Started.")

    def stop(self) -> None:
        """Stop the benchmark loop and close resources."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap:
            self._cap.release()
        if self._csv_file:
            self._csv_file.close()
        logger.info(f"[BenchmarkService] Stopped. Results saved to {self._csv_path}")

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_metrics(self) -> dict:
        gpu_mem = self._get_gpu_memory_mb()
        return {
            "YOLO11": {**self._yolo_bench.to_dict(), "gpu_memory_mb": gpu_mem},
            "RT-DETR-L": {**self._rtdetr_bench.to_dict(), "gpu_memory_mb": gpu_mem},
        }

    def get_mjpeg_frames(self):
        """MJPEG generator for the benchmark stream endpoint."""
        boundary = b"--frame\r\n"
        content_type = b"Content-Type: image/jpeg\r\n\r\n"
        while self._running:
            frame = self.get_latest_frame()
            if frame is None:
                time.sleep(0.03)
                continue
            ok, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.MJPEG_QUALITY]
            )
            if ok:
                yield boundary + content_type + jpeg.tobytes() + b"\r\n"
            time.sleep(1.0 / config.STREAM_FPS)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _benchmark_loop(self) -> None:
        """Main loop: read frame, run both models, annotate, emit CSV."""
        frame_idx = 0
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_idx += 1
            timestamp = datetime.utcnow().isoformat()

            # --- YOLO inference ---
            yolo_dets, yolo_lat = self._run_model(self._yolo, frame)
            self._yolo_bench.record(yolo_lat, len(yolo_dets))

            # --- RT-DETR inference ---
            rtdetr_dets, rtdetr_lat = self._run_model(self._rtdetr, frame)
            self._rtdetr_bench.record(rtdetr_lat, len(rtdetr_dets))

            # --- CSV ---
            self._write_csv(timestamp, frame_idx,
                            self._yolo_bench, self._rtdetr_bench)

            # --- Annotate ---
            annotated = self._draw_benchmark_hud(frame.copy(), yolo_dets, rtdetr_dets)

            with self._frame_lock:
                self._latest_frame = annotated

    @staticmethod
    def _run_model(
        detector: Optional[BaseDetector], frame: np.ndarray
    ) -> Tuple[List[Detection], float]:
        """Run a single model and return (detections, latency_ms)."""
        if detector is None or not detector.is_loaded:
            return [], 0.0
        t0 = time.perf_counter()
        dets = detector.predict(frame)
        latency = (time.perf_counter() - t0) * 1000
        return dets, latency

    def _draw_benchmark_hud(
        self,
        frame: np.ndarray,
        yolo_dets: List[Detection],
        rtdetr_dets: List[Detection],
    ) -> np.ndarray:
        """Overlay dual-model HUD panel on the frame."""
        h, w = frame.shape[:2]

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 130), (15, 15, 20), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        def _draw_column(x_offset: int, bench: ModelBenchmark, n_dets: int) -> None:
            colour_title = (0, 215, 255)
            colour_val = (220, 220, 220)
            cv2.putText(frame, bench.model_name, (x_offset, 22), _FONT, 0.65, colour_title, 2)
            cv2.putText(frame, f"FPS:     {bench.fps:.1f}", (x_offset, 48), _FONT, 0.5, colour_val, 1)
            cv2.putText(frame, f"Latency: {bench.avg_latency_ms:.1f}ms", (x_offset, 68), _FONT, 0.5, colour_val, 1)
            cv2.putText(frame, f"Objects: {n_dets}", (x_offset, 88), _FONT, 0.5, colour_val, 1)
            cv2.putText(frame, f"Frames:  {bench.frame_count}", (x_offset, 108), _FONT, 0.5, colour_val, 1)

        _draw_column(10, self._yolo_bench, len(yolo_dets))

        # Divider
        cv2.line(frame, (w // 2, 5), (w // 2, 125), (60, 60, 60), 1)

        _draw_column(w // 2 + 10, self._rtdetr_bench, len(rtdetr_dets))

        # Draw YOLO detections in blue, RTDETR in orange
        for det in yolo_dets:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 100, 50), 2)

        for det in rtdetr_dets:
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (50, 180, 255), 1)

        return frame

    def _open_csv(self) -> None:
        """Open CSV file and write header row."""
        write_header = not self._csv_path.exists()
        self._csv_file = open(self._csv_path, "a", newline="", encoding="utf-8")
        self._csv_writer = csv.writer(self._csv_file)
        if write_header:
            self._csv_writer.writerow(
                ["timestamp", "model", "frame", "fps", "latency_ms", "detections"]
            )

    def _write_csv(
        self,
        timestamp: str,
        frame_idx: int,
        yolo: ModelBenchmark,
        rtdetr: ModelBenchmark,
    ) -> None:
        if self._csv_writer is None:
            return
        # Write one row per model per frame
        self._csv_writer.writerow([
            timestamp, "YOLO11", frame_idx,
            round(yolo.fps, 2), round(yolo.avg_latency_ms, 2),
            int(yolo.detection_window[-1]) if yolo.detection_window else 0,
        ])
        self._csv_writer.writerow([
            timestamp, "RT-DETR-L", frame_idx,
            round(rtdetr.fps, 2), round(rtdetr.avg_latency_ms, 2),
            int(rtdetr.detection_window[-1]) if rtdetr.detection_window else 0,
        ])
        self._csv_file.flush()

    @staticmethod
    def _get_gpu_memory_mb() -> float:
        """Return current GPU memory usage in MB, or 0 if not available."""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.memory_allocated() / 1024 / 1024
        except Exception:
            pass
        return 0.0
