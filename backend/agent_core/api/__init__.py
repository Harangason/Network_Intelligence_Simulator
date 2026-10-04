"""Compatibility only; owner backend.nis.agent.api."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.api')
