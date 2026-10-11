"""Compatibility only; owner backend.nis.simulation.signals.derived.lookup."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.derived.lookup')
