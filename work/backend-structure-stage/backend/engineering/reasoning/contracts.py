"""Compatibility only; owner backend.nis.intelligence.engineering.reasoning.contracts."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.intelligence.engineering.reasoning.contracts')
