"""Compatibility only; owner backend.nis.interfaces.mcp.__main__."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.interfaces.mcp.__main__')
