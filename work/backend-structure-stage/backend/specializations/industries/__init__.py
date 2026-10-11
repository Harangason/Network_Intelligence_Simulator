"""Compatibility only; owner backend.nis.industries.catalog."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.catalog')
