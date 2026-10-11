"""Compatibility only; owner backend.nis.engineering.relations."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.relations')
