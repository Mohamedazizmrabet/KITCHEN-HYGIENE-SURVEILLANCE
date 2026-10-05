"""
tests/test_detectors.py — Smoke tests for the detector interface.

These tests validate the abstraction layer WITHOUT requiring model weights.
They mock the underlying model loading so the tests run in any environment.
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Add inference-service root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# BaseDetector tests
# ---------------------------------------------------------------------------

class TestBaseDetectorContract:
    """Verify the BaseDetector interface contract."""

    def test_detection_to_dict(self):
        """Detection.to_dict() returns the standard JSON schema."""
        from detectors.base_detector import Detection
        det = Detection(
            class_id=0,
            class_name="gloves",
            confidence=0.92,
            bbox=[10.0, 20.0, 100.0, 200.0],
            track_id=5,
        )
        d = det.to_dict()
        assert d["class_id"] == 0
        assert d["class_name"] == "gloves"
        assert d["confidence"] == 0.92
        assert len(d["bbox"]) == 4
        assert d["track_id"] == 5

    def test_detection_default_track_id(self):
        from detectors.base_detector import Detection
        det = Detection(class_id=1, class_name="hairnet", confidence=0.8, bbox=[0, 0, 50, 50])
        assert det.track_id is None

    def test_missing_model_file_raises(self, tmp_path):
        """safe_load() returns False when the model file doesn't exist."""
        from detectors.yolo_detector import YOLODetector
        detector = YOLODetector(
            model_path=tmp_path / "nonexistent.pt",
            device="cpu",
            confidence_threshold=0.5,
        )
        result = detector.safe_load()
        assert result is False
        assert not detector.is_loaded

    def test_predict_returns_empty_when_not_loaded(self):
        """predict() returns an empty list when model is not loaded."""
        from detectors.yolo_detector import YOLODetector
        detector = YOLODetector(
            model_path=Path("models/yolo11_model.pt"),
            device="cpu",
            confidence_threshold=0.5,
        )
        # Don't call safe_load — model is not loaded
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.predict(frame)
        assert detections == []


# ---------------------------------------------------------------------------
# RTDETRDetector tests
# ---------------------------------------------------------------------------

class TestRTDETRDetector:
    def test_missing_onnx_returns_false(self, tmp_path):
        from detectors.rtdetr_detector import RTDETRDetector
        detector = RTDETRDetector(
            model_path=tmp_path / "nonexistent.onnx",
            device="cpu",
            confidence_threshold=0.5,
        )
        assert detector.safe_load() is False
        assert not detector.is_loaded

    def test_predict_empty_when_unloaded(self):
        from detectors.rtdetr_detector import RTDETRDetector
        detector = RTDETRDetector(
            model_path=Path("models/rtdetrv2_model.onnx"),
            device="cpu",
            confidence_threshold=0.5,
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert detector.predict(frame) == []

    def test_preprocess_output_shape(self):
        """_preprocess() should return [1, 3, H, W] float32."""
        from detectors.rtdetr_detector import RTDETRDetector
        detector = RTDETRDetector(
            model_path=Path("models/rtdetrv2_model.onnx"),
            device="cpu",
            confidence_threshold=0.5,
        )
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        tensor = detector._preprocess(frame)
        assert tensor.shape == (1, 3, 640, 640)
        assert tensor.dtype == np.float32
        assert tensor.min() >= 0.0 and tensor.max() <= 1.0


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_device_resolves(self):
        """DEVICE resolves to either 'cuda' or 'cpu'."""
        import config
        assert config.DEVICE in {"cuda", "cpu"}

    def test_class_mapping_is_dict(self):
        import config
        assert isinstance(config.CLASS_MAPPING, dict)

    def test_violation_classes_are_strings(self):
        import config
        for cls in config.VIOLATION_CLASSES:
            assert isinstance(cls, str)
