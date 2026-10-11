"""Compatibility only; owner backend.nis.industries.generic_networking.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.generic_networking.manifest')
