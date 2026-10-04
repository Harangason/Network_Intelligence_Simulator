"""Compatibility only; owner backend.nis.agent.orchestration.local_reasoner."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.orchestration.local_reasoner')
