"""Compatibility only; owner backend.nis.engineering.routing.endpoint_consistency."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.routing.endpoint_consistency')
