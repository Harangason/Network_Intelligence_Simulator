"""Compatibility only; owner backend.nis.agent.api.input_output."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.api.input_output')
