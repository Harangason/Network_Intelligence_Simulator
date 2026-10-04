"""Compatibility only; owner backend.nis.knowledge.semantic_vocabulary."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.semantic_vocabulary')
