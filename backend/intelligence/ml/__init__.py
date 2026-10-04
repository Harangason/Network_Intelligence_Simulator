"""Compatibility only; owner backend.nis.intelligence.ml."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.intelligence.ml')
