"""
config.py — Central configuration module.

Reads from .env via python-dotenv and exposes typed settings
used across the entire inference service.
"""

import os
import torch
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the inference-service root
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

YOLO_MODEL_PATH = MODELS_DIR / os.getenv("YOLO_MODEL_PATH", "khawla_v6.pt").split("/")[-1]
PERSON_MODEL_PATH = MODELS_DIR / os.getenv("PERSON_MODEL_PATH", "yolov8n.pt").split("/")[-1]
MASK_MODEL_PATH = MODELS_DIR / os.getenv("MASK_MODEL_PATH", "khawla_mask_vest.pt").split("/")[-1]
RTDETR_MODEL_PATH = MODELS_DIR / os.getenv("RTDETR_MODEL_PATH", "rtdetr-l.pt").replace("\\", "/").split("/")[-1]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
IOU_THRESHOLD: float = float(os.getenv("IOU_THRESHOLD", "0.45"))


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------
def _resolve_device() -> str:
    """Resolve 'auto' to 'cuda' or 'cpu' based on hardware availability."""
    raw = os.getenv("DEVICE", "auto").lower()
    if raw == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return raw


DEVICE: str = _resolve_device()


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------
class ModelMode:
    YOLO = "YOLO"
    RTDETR = "RTDETR"
    BOTH = "BOTH"


DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", ModelMode.YOLO).upper()


# ---------------------------------------------------------------------------
# PPE Class Mapping & Normalisation
# ---------------------------------------------------------------------------

# Raw model class name -> normalised internal name used by tracker
# Covers both khawla_v6 (gloves/hairnet model) and khawla_mask_vest (mask model)
CLASS_NORMALISE: dict[str, str] = {
    # khawla_v6 classes
    "Glove":         "gloves",
    "Bare Hand":     "no_gloves",   # bare hand = violation (no gloves)
    "Hairnet":       "hairnet",
    "Bare Hair":     "no_hairnet",  # bare hair = violation (no hairnet)
    # khawla_mask_vest classes
    "Mask":          "mask",
    "NO-Mask":       "no_mask",
    "Person":        "person",
    # keremberke fallbacks (kept for backwards compat)
    "gloves":        "gloves",
    "mask":          "mask",
    "no_gloves":     "no_gloves",
    "no_mask":       "no_mask",
    "hairnet":       "hairnet",
    "no_hairnet":    "no_hairnet",
}

# Legacy CLASS_MAPPING (kept for botsort _is_person lookup)
CLASS_MAPPING: dict[int, str] = {}

# Classes that represent PPE compliance (shown in green)
COMPLIANCE_CLASSES: set[str] = {
    "gloves",
    "hairnet",
    "mask",
}

# Classes that represent a PPE violation (shown in red)
VIOLATION_CLASSES: set[str] = {
    "no_gloves",
    "no_hairnet",
    "no_mask",
}


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------
STREAM_FPS: int = int(os.getenv("STREAM_FPS", "30"))
MJPEG_QUALITY: int = int(os.getenv("MJPEG_QUALITY", "85"))


# ---------------------------------------------------------------------------
# FastAPI server
# ---------------------------------------------------------------------------
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8001"))


# ---------------------------------------------------------------------------
# External services
# ---------------------------------------------------------------------------
LARAVEL_BASE_URL: str = os.getenv("LARAVEL_BASE_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
BENCHMARK_CSV_PATH: Path = LOGS_DIR / Path(os.getenv("BENCHMARK_CSV_PATH", "logs/benchmark.csv")).name
