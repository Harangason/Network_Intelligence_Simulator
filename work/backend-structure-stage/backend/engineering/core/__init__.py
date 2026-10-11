"""Compatibility only; owner backend.nis.domain.core."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.domain.core')
