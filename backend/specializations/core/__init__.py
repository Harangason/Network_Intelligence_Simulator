"""Compatibility only; owner backend.nis.specializations.core."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.specializations.core')
