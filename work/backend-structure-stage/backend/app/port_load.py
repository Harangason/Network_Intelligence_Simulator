"""Compatibility only; owner backend.nis.simulation.port_load."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.port_load')
