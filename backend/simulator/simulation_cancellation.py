"""Compatibility only; owner backend.nis.simulation.simulation_cancellation."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.simulation_cancellation')
