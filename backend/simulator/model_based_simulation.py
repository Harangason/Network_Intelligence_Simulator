"""Compatibility only; owner backend.nis.simulation.model_based_simulation."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.model_based_simulation')
