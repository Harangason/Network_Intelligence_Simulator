"""Compatibility only; owner backend.nis.traces.trace_sessions."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.traces.trace_sessions')
