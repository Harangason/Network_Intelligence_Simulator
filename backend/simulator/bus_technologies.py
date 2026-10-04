"""Compatibility only; owner backend.nis.simulation.bus_technologies."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.bus_technologies')
