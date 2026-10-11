"""Compatibility only; owner backend.nis.physics."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.physics')
