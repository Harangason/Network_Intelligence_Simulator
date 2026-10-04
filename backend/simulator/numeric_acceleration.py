"""Compatibility only; owner backend.nis.simulation.numeric_acceleration."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.numeric_acceleration')
