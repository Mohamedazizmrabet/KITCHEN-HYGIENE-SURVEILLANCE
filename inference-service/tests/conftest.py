"""
tests/conftest.py — Pytest configuration and shared fixtures.
"""

import sys
from pathlib import Path

# Ensure inference-service root is on the Python path so all imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))
