"""
detectors/__init__.py — Detector package exports.
"""

from .base_detector import BaseDetector, Detection
from .yolo_detector import YOLODetector
from .rtdetr_detector import RTDETRDetector

__all__ = ["BaseDetector", "Detection", "YOLODetector", "RTDETRDetector"]
