"""Compatibility only; owner backend.nis.industries.legacy_projection.registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.legacy_projection.registry')
