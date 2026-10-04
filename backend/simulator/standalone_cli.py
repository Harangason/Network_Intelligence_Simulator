"""Compatibility only; owner backend.nis.interfaces.cli.standalone."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.interfaces.cli.standalone')
