"""Make the relocated flat simulator modules importable during tests."""

import sys
from pathlib import Path


SIMULATOR_ROOT = Path(__file__).resolve().parents[1] / "simulator"
sys.path.insert(0, str(SIMULATOR_ROOT))
