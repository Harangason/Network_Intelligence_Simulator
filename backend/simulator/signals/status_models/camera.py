"""Compatibility only; owner backend.nis.simulation.signals.status_models.camera."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.status_models.camera')
