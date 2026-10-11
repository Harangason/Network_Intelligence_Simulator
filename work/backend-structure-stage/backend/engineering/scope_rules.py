"""Compatibility only; owner backend.nis.engineering.scope_rules."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.scope_rules')
