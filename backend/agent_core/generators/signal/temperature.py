"""Compatibility only; owner backend.nis.agent.generators.signal.temperature."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.generators.signal.temperature')
