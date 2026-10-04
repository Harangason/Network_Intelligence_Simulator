"""Compatibility only; owner backend.nis.simulation.transport_dependencies."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.transport_dependencies')
