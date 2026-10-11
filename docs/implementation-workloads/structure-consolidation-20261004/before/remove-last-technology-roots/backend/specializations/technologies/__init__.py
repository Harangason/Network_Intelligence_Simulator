"""Compatibility only; owner backend.nis.communication.ownership."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.communication.ownership')
