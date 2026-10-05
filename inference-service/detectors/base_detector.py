"""
detectors/base_detector.py — Abstract detector interface.

Every model implementation (YOLO, RT-DETR, future models) must
subclass BaseDetector and implement the predict() method.

The rest of the application only ever interacts with BaseDetector,
making model swapping fully transparent.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detection result dataclass
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """A single object detection result.

    Attributes:
        class_id:    Integer class index as produced by the model.
        class_name:  Human-readable label resolved from CLASS_MAPPING.
        confidence:  Detection confidence in [0, 1].
        bbox:        Bounding box as [x1, y1, x2, y2] in pixel coords.
        track_id:    Optional persistent tracking ID assigned by BoT-SORT.
    """

    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]
    track_id: int | None = None

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dictionary."""
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": [round(v, 2) for v in self.bbox],
            "track_id": self.track_id,
        }


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class BaseDetector(ABC):
    """Common interface for all detection models.

    Subclasses must implement:
        - load_model(): initialise the underlying framework/weights
        - predict(frame): run inference and return List[Detection]

    Design contract:
        * predict() MUST return an empty list when no detections are found.
        * predict() MUST NOT raise exceptions for normal empty-frame results.
        * If the model weights file is missing, load_model() MUST raise
          FileNotFoundError with a descriptive message telling the user
          where to place the file.
    """

    def __init__(self, model_path: Path, device: str, confidence_threshold: float) -> None:
        self.model_path = model_path
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._is_loaded: bool = False

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def load_model(self) -> None:
        """Load the model weights from self.model_path.

        Raises:
            FileNotFoundError: if the weight file does not exist.
            RuntimeError: if the model fails to initialise.
        """

    @abstractmethod
    def predict(self, frame: np.ndarray) -> List[Detection]:
        """Run inference on a single BGR frame (as produced by OpenCV).

        Args:
            frame: H×W×3 uint8 numpy array in BGR colour space.

        Returns:
            List of Detection objects. Empty list if nothing detected.
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def _check_model_file(self) -> None:
        """Raise a clear FileNotFoundError if the weight file is missing."""
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"\n{'='*60}\n"
                f"  MODEL FILE NOT FOUND\n"
                f"  Expected path: {self.model_path.resolve()}\n\n"
                f"  To fix this:\n"
                f"  1. Obtain your trained model weights.\n"
                f"  2. Place the file at the path shown above.\n"
                f"  3. Restart the inference service.\n"
                f"{'='*60}\n"
            )

    def safe_load(self) -> bool:
        """Attempt to load the model, returning False instead of crashing.

        Returns:
            True if the model loaded successfully, False otherwise.
            Logs a user-friendly error message on failure.
        """
        try:
            self._check_model_file()
            self.load_model()
            self._is_loaded = True
            logger.info(f"[{self.__class__.__name__}] Model loaded from {self.model_path}")
            return True
        except FileNotFoundError as exc:
            logger.error(str(exc))
            return False
        except Exception as exc:
            logger.error(
                f"[{self.__class__.__name__}] Failed to load model: {exc}\n"
                f"The service will continue running but detections will be disabled."
            )
            return False

    def __repr__(self) -> str:
        status = "loaded" if self._is_loaded else "NOT LOADED — weights missing"
        return f"{self.__class__.__name__}(device={self.device}, status={status})"
