"""Compatibility only; owner backend.nis.intelligence.ml.core.registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.intelligence.ml.core.registry')
