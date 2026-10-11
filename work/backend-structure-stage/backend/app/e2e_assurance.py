"""Compatibility only; owner backend.nis.simulation.e2e_assurance."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.e2e_assurance')
