"""Compatibility only; owner backend.nis.engineering.tool_registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.tool_registry')
