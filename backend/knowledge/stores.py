"""Compatibility only; owner backend.nis.knowledge.stores."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.stores')
