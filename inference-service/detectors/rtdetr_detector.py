from __future__ import annotations

import logging
from typing import List

import numpy as np

import config
from detectors.base_detector import BaseDetector, Detection

logger = logging.getLogger(__name__)


class RTDETRDetector(BaseDetector):
    """Run a genuine Ultralytics RT-DETR checkpoint independently of YOLO."""

    def load_model(self) -> None:
        try:
            from ultralytics import RTDETR
        except ImportError as exc:
            raise RuntimeError("Ultralytics with RT-DETR support is required") from exc

        self._check_model_file()
        logger.info("[RTDETRDetector] Loading RT-DETR weights from %s", self.model_path)
        self._model = RTDETR(str(self.model_path))
        self._warmup()

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if not self._is_loaded or self._model is None:
            return []

        try:
            results = self._model.predict(
                source=frame,
                conf=self.confidence_threshold,
                device=self.device,
                verbose=False,
            )
            return self._parse_results(results)
        except Exception as exc:
            logger.error("[RTDETRDetector] Inference error: %s", exc)
            return []

    def _parse_results(self, results) -> List[Detection]:
        detections: List[Detection] = []
        names = self._model.names
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)
            for bbox, confidence, class_id in zip(boxes, confidences, class_ids):
                raw_name = names.get(int(class_id), f"class_{class_id}")
                normalized_name = config.CLASS_NORMALISE.get(raw_name, raw_name.lower())
                detections.append(
                    Detection(
                        class_id=int(class_id),
                        class_name=normalized_name,
                        confidence=float(confidence),
                        bbox=bbox.tolist(),
                    )
                )
        return detections

    def _warmup(self) -> None:
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(
                source=dummy,
                conf=0.99,
                device=self.device,
                verbose=False,
            )
            logger.info("[RTDETRDetector] Warmup complete.")
        except Exception as exc:
            logger.warning("[RTDETRDetector] Warmup failed: %s", exc)
