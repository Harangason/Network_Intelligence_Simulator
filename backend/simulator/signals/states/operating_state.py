"""Compatibility only; owner backend.nis.simulation.signals.states.operating_state."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.states.operating_state')
