"""Compatibility only; owner backend.nis.infrastructure.paths."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.infrastructure.paths')
