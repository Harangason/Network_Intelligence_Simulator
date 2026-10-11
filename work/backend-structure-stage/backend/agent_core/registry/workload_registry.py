"""Compatibility only; owner backend.nis.agent.registry.workload_registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.registry.workload_registry')
