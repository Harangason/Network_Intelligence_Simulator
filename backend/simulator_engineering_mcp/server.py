"""Compatibility only; owner backend.nis.interfaces.mcp.server."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.interfaces.mcp.server')
