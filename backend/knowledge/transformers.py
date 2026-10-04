"""Compatibility only; owner backend.nis.knowledge.transformers."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.transformers')
