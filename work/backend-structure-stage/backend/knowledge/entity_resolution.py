"""Compatibility only; owner backend.nis.knowledge.entity_resolution."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.entity_resolution')
