"""Compatibility only; owner backend.nis.agent.core."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.core')
