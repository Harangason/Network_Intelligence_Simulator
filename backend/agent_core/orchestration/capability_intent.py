"""Compatibility only; owner backend.nis.agent.orchestration.capability_intent."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.orchestration.capability_intent')
