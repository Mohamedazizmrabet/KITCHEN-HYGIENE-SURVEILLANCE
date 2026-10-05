from __future__ import annotations
import logging
from pathlib import Path
from typing import List
import numpy as np
import config
from detectors.base_detector import BaseDetector, Detection

logger = logging.getLogger(__name__)


class YOLODetector(BaseDetector):
    def __init__(self, model_path, device, confidence_threshold):
        super().__init__(model_path, device, confidence_threshold)

    def load_model(self):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError('Ultralytics not installed') from exc
        self._check_model_file()
        logger.info(f'[YOLODetector] PPE model: {self.model_path}')
        self._model = YOLO(str(self.model_path))
        self._mask_model = None
        if hasattr(config, 'MASK_MODEL_PATH') and config.MASK_MODEL_PATH.exists():
            logger.info(f'[YOLODetector] Mask model: {config.MASK_MODEL_PATH}')
            self._mask_model = YOLO(str(config.MASK_MODEL_PATH))
        self._person_model = None
        if hasattr(config, 'PERSON_MODEL_PATH') and config.PERSON_MODEL_PATH.exists():
            logger.info(f'[YOLODetector] Person model: {config.PERSON_MODEL_PATH}')
            self._person_model = YOLO(str(config.PERSON_MODEL_PATH))
        self._warmup()

    def predict(self, frame):
        if not self._is_loaded or self._model is None:
            return []
        all_detections = []
        try:
            results = self._model.predict(source=frame, conf=self.confidence_threshold, device=self.device, verbose=False)
            all_detections.extend(self._parse_results(results, self._model))
        except Exception as exc:
            logger.error(f'[YOLODetector] PPE error: {exc}')
        if getattr(self, '_mask_model', None) is not None:
            try:
                mask_results = self._mask_model.predict(source=frame, conf=self.confidence_threshold, device=self.device, verbose=False)
                for det in self._parse_results(mask_results, self._mask_model):
                    if det.class_name in {'mask', 'no_mask', 'person'}:
                        all_detections.append(det)
            except Exception as exc:
                logger.error(f'[YOLODetector] Mask error: {exc}')
        if getattr(self, '_person_model', None) is not None:
            try:
                person_results = self._person_model.predict(source=frame, conf=self.confidence_threshold, device=self.device, classes=[0], verbose=False)
                all_detections.extend(self._parse_results(person_results, self._person_model))
            except Exception as exc:
                logger.error(f'[YOLODetector] Person error: {exc}')
        return all_detections

    def _parse_results(self, results, model):
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)
            for bbox, conf, cls_id in zip(boxes, confidences, class_ids):
                raw_name = model.names.get(cls_id, f'class_{cls_id}')
                class_name = config.CLASS_NORMALISE.get(raw_name, raw_name.lower())
                detections.append(Detection(class_id=int(cls_id), class_name=class_name, confidence=float(conf), bbox=bbox.tolist()))
        return detections

    def _warmup(self):
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(source=dummy, conf=0.99, device=self.device, verbose=False)
            if getattr(self, '_mask_model', None) is not None:
                self._mask_model.predict(source=dummy, conf=0.99, device=self.device, verbose=False)
            if getattr(self, '_person_model', None) is not None:
                self._person_model.predict(source=dummy, conf=0.99, device=self.device, verbose=False)
            logger.info('[YOLODetector] Warmup complete.')
        except Exception as exc:
            logger.warning(f'[YOLODetector] Warmup failed: {exc}')
