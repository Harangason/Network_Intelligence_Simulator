"""Compatibility only; owner backend.nis.simulation.signals.physical.common."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.physical.common')
