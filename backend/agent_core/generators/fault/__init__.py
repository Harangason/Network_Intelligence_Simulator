"""Compatibility only; owner backend.nis.agent.generators.fault."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.generators.fault')
