"""Compatibility only; owner backend.nis.intelligence.engineering.intelligence.repository."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.intelligence.engineering.intelligence.repository')
