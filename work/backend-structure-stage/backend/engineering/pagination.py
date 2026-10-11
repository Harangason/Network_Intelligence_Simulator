"""Compatibility only; owner backend.nis.engineering.pagination."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.pagination')
