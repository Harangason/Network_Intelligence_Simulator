"""Compatibility only; owner backend.nis.simulation.filter_system."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.filter_system')
