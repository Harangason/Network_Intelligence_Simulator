"""Compatibility only; owner backend.nis.agent.registry.handler_registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.registry.handler_registry')
