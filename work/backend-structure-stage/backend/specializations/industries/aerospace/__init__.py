"""Compatibility only; owner backend.nis.industries.aerospace.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.aerospace.manifest')
