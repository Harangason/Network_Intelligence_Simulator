"""Compatibility only; owner backend.nis.app."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.app')
