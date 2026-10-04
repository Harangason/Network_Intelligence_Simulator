"""Compatibility only; owner backend.nis.intelligence.ml.training."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.intelligence.ml.training')
