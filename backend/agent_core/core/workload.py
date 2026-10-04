"""Compatibility only; owner backend.nis.agent.core.workload."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.core.workload')
