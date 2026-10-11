"""Compatibility only; owner backend.nis.domain.vocabulary."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.domain.vocabulary')
