"""Compatibility only; owner backend.nis.agent.core.completion."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.core.completion')
