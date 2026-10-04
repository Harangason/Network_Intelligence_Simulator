"""Compatibility only; owner backend.nis.simulation.service."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.service')
