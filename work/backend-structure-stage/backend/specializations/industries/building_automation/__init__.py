"""Compatibility only; owner backend.nis.industries.building_automation.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.building_automation.manifest')
