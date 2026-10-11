"""Compatibility only; owner backend.nis.traces.universal_trace."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.traces.universal_trace')
