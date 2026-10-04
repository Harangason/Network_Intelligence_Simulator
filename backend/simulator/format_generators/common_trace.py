"""Compatibility only; owner backend.nis.traces.formats.common_trace."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.traces.formats.common_trace')
