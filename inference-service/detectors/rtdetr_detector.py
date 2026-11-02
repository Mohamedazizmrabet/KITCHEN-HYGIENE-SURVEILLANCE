from __future__ import annotations

import logging
from typing import List

import cv2
import numpy as np

import config
from detectors.base_detector import BaseDetector, Detection

logger = logging.getLogger(__name__)


class RTDETRDetector(BaseDetector):
    """Run an RT-DETR model independently of YOLO.

    Two weight formats are supported:
        * a directory (Hugging Face Transformers model, e.g. models/rtdetr-cppe5)
        * a .pt file (Ultralytics checkpoint, e.g. models/rtdetr-l.pt)
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._processor = None
        self._person_model = None

    @property
    def _uses_transformers(self) -> bool:
        return self.model_path.is_dir()

    @property
    def supported_ppe(self) -> set[str] | None:
        """PPE classes this model can detect (CPPE-5 has no hairnet)."""
        return {"gloves", "mask"} if self._uses_transformers else None

    def load_model(self) -> None:
        self._check_model_file()
        if self._uses_transformers:
            self._load_transformers()
        else:
            self._load_ultralytics()
        self._warmup()

    def _load_ultralytics(self) -> None:
        try:
            from ultralytics import RTDETR
        except ImportError as exc:
            raise RuntimeError("Ultralytics with RT-DETR support is required") from exc

        logger.info("[RTDETRDetector] Loading Ultralytics RT-DETR weights from %s", self.model_path)
        self._model = RTDETR(str(self.model_path))

    def _load_transformers(self) -> None:
        try:
            from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
        except ImportError as exc:
            raise RuntimeError("transformers is required for Hugging Face RT-DETR models") from exc

        logger.info("[RTDETRDetector] Loading Hugging Face RT-DETR model from %s", self.model_path)
        self._processor = RTDetrImageProcessor.from_pretrained(str(self.model_path))
        self._model = RTDetrForObjectDetection.from_pretrained(str(self.model_path))
        self._model.to(self.device).eval()

        # The PPE model has no person class, so the tracker needs persons from
        # the same YOLO person model the YOLO path uses.
        if config.PERSON_MODEL_PATH.exists():
            from ultralytics import YOLO
            logger.info("[RTDETRDetector] Person model: %s", config.PERSON_MODEL_PATH)
            self._person_model = YOLO(str(config.PERSON_MODEL_PATH))

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if not self._is_loaded or self._model is None:
            return []

        try:
            if self._uses_transformers:
                return self._predict_transformers(frame)
            results = self._model.predict(
                source=frame,
                conf=self.confidence_threshold,
                device=self.device,
                verbose=False,
            )
            return self._parse_results(results, self._model.names)
        except Exception as exc:
            logger.error("[RTDETRDetector] Inference error: %s", exc)
            return []

    def _predict_transformers(self, frame: np.ndarray) -> List[Detection]:
        import torch

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        inputs = self._processor(images=rgb, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self._model(**inputs)
        result = self._processor.post_process_object_detection(
            outputs,
            target_sizes=[frame.shape[:2]],
            threshold=self.confidence_threshold,
        )[0]

        detections: List[Detection] = []
        names = self._model.config.id2label
        for score, label, box in zip(result["scores"], result["labels"], result["boxes"]):
            class_id = int(label)
            raw_name = names.get(class_id, f"class_{class_id}")
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=config.CLASS_NORMALISE.get(raw_name, raw_name.lower()),
                    confidence=float(score),
                    bbox=box.cpu().tolist(),
                )
            )

        if self._person_model is not None:
            person_results = self._person_model.predict(
                source=frame,
                conf=self.confidence_threshold,
                device=self.device,
                classes=[0],
                verbose=False,
            )
            detections.extend(self._parse_results(person_results, self._person_model.names))
        return detections

    def _parse_results(self, results, names) -> List[Detection]:
        detections: List[Detection] = []
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
            if self._uses_transformers:
                self._predict_transformers(dummy)
            else:
                self._model.predict(
                    source=dummy,
                    conf=0.99,
                    device=self.device,
                    verbose=False,
                )
            logger.info("[RTDETRDetector] Warmup complete.")
        except Exception as exc:
            logger.warning("[RTDETRDetector] Warmup failed: %s", exc)
