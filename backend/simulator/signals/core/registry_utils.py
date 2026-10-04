"""Compatibility only; owner backend.nis.simulation.signals.core.registry_utils."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.core.registry_utils')
