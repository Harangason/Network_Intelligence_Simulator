"""Compatibility only; owner backend.nis.engineering.structure.zoning_service."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.structure.zoning_service')
