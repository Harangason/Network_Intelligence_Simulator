"""Compatibility only; owner backend.nis.simulation.signals.noise.sensor_noise."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.noise.sensor_noise')
