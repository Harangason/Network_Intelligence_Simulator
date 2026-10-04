"""Compatibility only; owner backend.nis.engineering.routing.retrieval."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.routing.retrieval')
