"""Compatibility only; owner backend.nis.simulation.runtime_analysis."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.runtime_analysis')
