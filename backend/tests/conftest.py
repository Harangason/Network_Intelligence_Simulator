"""Make the relocated flat simulator modules importable during tests."""

import sys
from pathlib import Path


SIMULATOR_ROOT = Path(__file__).resolve().parents[1] / "simulator"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SIMULATOR_ROOT))
