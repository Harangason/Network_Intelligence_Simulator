"""Compatibility only; owner backend.nis.engineering.proposals."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.proposals')
