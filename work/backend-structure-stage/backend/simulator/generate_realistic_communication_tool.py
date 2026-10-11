"""Compatibility only; owner backend.nis.simulation.communication_generator."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.communication_generator')
