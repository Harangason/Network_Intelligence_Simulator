"""Compatibility only; owner backend.nis.industries.industrial_automation.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.industrial_automation.manifest')
