"""Compatibility only; owner backend.nis.agent.handlers.routing."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.handlers.routing')
