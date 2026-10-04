"""Compatibility only; owner backend.nis.engineering.performance_governance."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.performance_governance')
