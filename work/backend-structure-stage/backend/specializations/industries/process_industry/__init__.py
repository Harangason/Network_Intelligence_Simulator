"""Compatibility only; owner backend.nis.industries.process_industry.manifest."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.process_industry.manifest')
