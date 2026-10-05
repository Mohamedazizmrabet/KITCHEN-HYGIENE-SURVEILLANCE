"""
Quick test: open the Ivideon embed, force-play, and save 3 frames to disk
to verify the video is actually playing (not just showing a paused poster).
Run with: venv\Scripts\python.exe test_playwright_capture.py
"""
import cv2
import numpy as np
from services.stream_utils import capture_embedded_player, EmbeddedCaptureConfig

URL = "https://open.ivideon.com/embed/v2/?server=100-3f1933bc335aed64e3a0a0ead67bca0e&camera=0&lang=en"

cfg = EmbeddedCaptureConfig(url=URL, fps=2.0, width=1280, height=720, headless=False)

print("Starting capture... (headless=False so you can watch it)")
gen = capture_embedded_player(cfg)

for i, frame in enumerate(gen):
    path = f"test_frame_{i}.jpg"
    cv2.imwrite(path, frame)
    print(f"Saved {path}  shape={frame.shape}")
    if i >= 4:
        break

print("Done. Check test_frame_*.jpg to see if the video is playing.")
