"""Compatibility only; owner backend.nis.simulation.signals.physical.current."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.physical.current')
