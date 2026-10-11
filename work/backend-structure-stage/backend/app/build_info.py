"""Compatibility only; owner backend.nis.app.build_info."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.app.build_info')
