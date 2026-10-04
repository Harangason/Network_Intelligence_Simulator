"""Compatibility only; owner backend.nis.specializations.core.models."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.specializations.core.models')
