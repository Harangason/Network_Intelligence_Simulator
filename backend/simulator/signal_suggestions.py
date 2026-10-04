"""Compatibility only; owner backend.nis.simulation.signal_suggestions."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signal_suggestions')
