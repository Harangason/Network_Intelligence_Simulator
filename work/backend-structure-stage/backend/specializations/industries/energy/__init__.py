"""Compatibility only; owner backend.nis.industries.energy.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.energy.manifest')
