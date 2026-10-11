"""Compatibility only; owner backend.nis.agent.tools.simulation_gateway."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.tools.simulation_gateway')
