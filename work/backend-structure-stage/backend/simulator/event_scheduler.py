"""Compatibility only; owner backend.nis.simulation.runtime.event_scheduler."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.runtime.event_scheduler')
