"""Compatibility only; owner backend.nis.simulation.hardware_profile."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.hardware_profile')
