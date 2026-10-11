"""Compatibility only; owner backend.nis.app.__main__."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.app.__main__')
