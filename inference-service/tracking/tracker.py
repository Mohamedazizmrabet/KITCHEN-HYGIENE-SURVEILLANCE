"""
tracking/tracker.py — BoT-SORT multi-object tracker + PPE compliance logic.

Uses the Ultralytics tracking API (botsort.yaml) to assign persistent
track IDs to persons across frames.

For each tracked person, the compliance engine:
  - collects PPE detections within proximity
  - determines COMPLIANT or VIOLATION status
  - maintains a rolling history window
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config
from detectors.base_detector import Detection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TrackState:
    """Accumulated state for a single tracked person."""
    track_id: int
    bbox: List[float]                  # [x1, y1, x2, y2] last seen
    detected_ppe: List[str] = field(default_factory=list)
    missing_ppe: List[str] = field(default_factory=list)
    is_compliant: bool = True
    frames_seen: int = 0
    last_frame: int = 0

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "bbox": self.bbox,
            "detected_ppe": self.detected_ppe,
            "missing_ppe": self.missing_ppe,
            "status": "COMPLIANT" if self.is_compliant else "VIOLATION",
            "frames_seen": self.frames_seen,
        }


# ---------------------------------------------------------------------------
# PPE Tracker
# ---------------------------------------------------------------------------

class PPETracker:
    """Wraps Ultralytics BoT-SORT and adds PPE compliance logic.

    Tracking is performed on the full detection list (persons + PPE items).
    Person tracks are identified and PPE detections are spatially associated
    with the nearest person track.

    Args:
        device:     Torch device string ('cuda' or 'cpu').
        reid_weights: Optional path to ReID weights. Defaults to BoT-SORT defaults.
        history_len: Number of frames to keep in rolling history.
    """

    def __init__(
        self,
        device: str = "cpu",
        history_len: int = 30,
    ) -> None:
        self.device = device
        self.history_len = history_len
        self._tracker = None
        self._track_states: Dict[int, TrackState] = {}
        self._frame_count: int = 0
        self._init_tracker()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_tracker(self) -> None:
        """Initialise BoT-SORT via Ultralytics."""
        try:
            from ultralytics.trackers.bot_sort import BOTSORT
            from ultralytics.cfg import get_cfg
            from ultralytics.utils.checks import check_yaml

            # Load default tracking config from ultralytics
            cfg = get_cfg(check_yaml('botsort.yaml'))
            
            # Override with our specific stream framerate
            cfg.frame_rate = config.STREAM_FPS
            
            self._tracker = BOTSORT(cfg)
            logger.info("[PPETracker] BoT-SORT initialised.")
        except Exception as exc:
            logger.warning(
                f"[PPETracker] Could not initialise BoT-SORT ({exc}). "
                f"Falling back to detection-only mode (no persistent IDs)."
            )
            self._tracker = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self, detections: List[Detection], frame: np.ndarray
    ) -> List[TrackState]:
        """Update tracker with new detections and return track states.

        Args:
            detections: List of Detection objects from the active model.
            frame:      The current BGR frame (used by ReID internally).

        Returns:
            List of TrackState for all currently active persons.
        """
        self._frame_count += 1

        if self._tracker is None or not detections:
            return list(self._track_states.values())

        try:
            tracked = self._run_botsort(detections, frame)
        except Exception as exc:
            logger.debug(f"[PPETracker] Tracker update error: {exc}")
            tracked = []

        # Separate person tracks from PPE detections
        person_tracks = []
        for t in tracked:
            # ultralytics tracker.update returns numpy array: [x1, y1, x2, y2, id, conf, cls, ...]
            track_dict = {
                "bbox": t[:4].tolist(),
                "track_id": int(t[4]),
                "conf": float(t[5]),
                "cls": int(t[6])
            }
            if self._is_person(track_dict):
                person_tracks.append(track_dict)
                
        ppe_detections = [d for d in detections if not self._is_person(d)]

        # Update states for tracked persons
        active_ids = set()
        for track in person_tracks:
            tid = int(track["track_id"])
            active_ids.add(tid)
            state = self._track_states.setdefault(
                tid, TrackState(track_id=tid, bbox=track["bbox"])
            )
            state.bbox = track["bbox"]
            state.frames_seen += 1
            state.last_frame = self._frame_count

            # Associate nearby PPE detections
            detected, missing = self._evaluate_compliance(state.bbox, ppe_detections)
            state.detected_ppe = detected
            state.missing_ppe = missing
            state.is_compliant = len(missing) == 0

        # Prune stale tracks (not seen in last 2× history window)
        stale_threshold = self._frame_count - self.history_len * 2
        self._track_states = {
            tid: s
            for tid, s in self._track_states.items()
            if s.last_frame > stale_threshold or tid in active_ids
        }

        return list(self._track_states.values())

    def get_all_states(self) -> List[TrackState]:
        """Return the current state of all known tracks."""
        return list(self._track_states.values())

    def reset(self) -> None:
        """Clear all tracking state."""
        self._track_states.clear()
        self._frame_count = 0
        self._init_tracker()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_botsort(self, detections: List[Detection], frame: np.ndarray):
        """Convert detections to BoT-SORT format and run update step."""
        import torch
        from ultralytics.engine.results import Boxes

        if not detections:
            return []

        # BoT-SORT expects [x1, y1, x2, y2, conf, cls]
        dets = []
        for d in detections:
            dets.append([*d.bbox, d.confidence, float(d.class_id)])

        det_tensor = torch.tensor(dets, dtype=torch.float32)
        h, w = frame.shape[:2]
        boxes = Boxes(det_tensor, (h, w))
        return self._tracker.update(boxes, frame)

    @staticmethod
    def _is_person(obj) -> bool:
        """Determine if a detection/track represents a person."""
        name = ""
        # 1) If obj is a track dictionary
        if isinstance(obj, dict):
            cls_id = obj["cls"]
            name = config.CLASS_MAPPING.get(cls_id, "").lower()
            if not name and cls_id == 0:
                name = "person"
        # 2) If obj is a Detection object
        elif hasattr(obj, "class_name"):
            name = obj.class_name.lower()
            # If class mapping is provided, check if ID 0 is person
            if not name and obj.class_id == 0 and config.CLASS_MAPPING.get(0, "").lower() == "person":
                name = "person"

        if "person" in name:
            return True
        return False

    @staticmethod
    def _iou(box_a: List[float], box_b: List[float]) -> float:
        """Compute IoU between two [x1,y1,x2,y2] boxes."""
        xa1, ya1, xa2, ya2 = box_a
        xb1, yb1, xb2, yb2 = box_b

        inter_x1 = max(xa1, xb1)
        inter_y1 = max(ya1, yb1)
        inter_x2 = min(xa2, xb2)
        inter_y2 = min(ya2, yb2)

        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        area_a = (xa2 - xa1) * (ya2 - ya1)
        area_b = (xb2 - xb1) * (yb2 - yb1)
        union = area_a + area_b - inter_area

        return inter_area / (union + 1e-6)

    def _evaluate_compliance(
        self, person_bbox: List[float], ppe_detections: List[Detection]
    ) -> Tuple[List[str], List[str]]:
        """Determine which PPE items are present/missing for a person.

        Reads COMPLIANCE_CLASSES and VIOLATION_CLASSES from config each call
        so the user can toggle them live via the API.

        Returns:
            (detected_ppe, missing_ppe)
        """
        # Read config dynamically so API toggles take effect immediately
        compliance_classes = config.COMPLIANCE_CLASSES
        violation_classes = config.VIOLATION_CLASSES

        px1, py1, px2, py2 = person_bbox
        pw = px2 - px1
        ph = py2 - py1

        # Expand person box by 20% in each direction for looser association
        exp = 0.2
        ex1, ey1 = px1 - pw * exp, py1 - ph * exp
        ex2, ey2 = px2 + pw * exp, py2 + ph * exp

        detected_ppe: List[str] = []
        violation_found: List[str] = []

        for ppe in ppe_detections:
            if ppe.class_name not in compliance_classes and \
               ppe.class_name not in violation_classes:
                continue

            # Check if PPE centroid is within expanded person box
            cx = (ppe.bbox[0] + ppe.bbox[2]) / 2
            cy = (ppe.bbox[1] + ppe.bbox[3]) / 2
            if ex1 <= cx <= ex2 and ey1 <= cy <= ey2:
                detected_ppe.append(ppe.class_name)
                if ppe.class_name in violation_classes:
                    violation_found.append(ppe.class_name)

        # Determine which compliance classes are missing and return their violation strings
        missing: List[str] = [
            f"no_{cls}" for cls in compliance_classes
            if cls not in detected_ppe
        ]
        
        # Merge explicitly detected violations (e.g. if 'no_mask' was detected directly)
        for v in violation_found:
            if v not in missing:
                missing.append(v)

        # Build friendly display list: what we DID find (compliance items only)
        found_compliance = [p for p in detected_ppe if p in compliance_classes]

        return found_compliance, missing
