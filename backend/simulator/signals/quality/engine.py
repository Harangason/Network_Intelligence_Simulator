"""Compatibility only; owner backend.nis.simulation.signals.quality.engine."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.quality.engine')
