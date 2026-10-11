"""Compatibility only; owner backend.nis.app.runtime_config."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.app.runtime_config')
