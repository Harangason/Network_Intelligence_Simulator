"""Compatibility projection; no technical definitions."""
import sys
from backend.nis.communication import catalog
sys.modules[__name__] = catalog
