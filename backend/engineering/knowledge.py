"""Compatibility only; owner backend.nis.engineering.knowledge."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.knowledge')
