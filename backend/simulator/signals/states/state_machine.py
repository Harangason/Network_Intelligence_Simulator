"""Compatibility only; owner backend.nis.simulation.signals.states.state_machine."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.signals.states.state_machine')
