"""Compatibility only; owner backend.nis.simulation.communication_simulator."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.communication_simulator')
