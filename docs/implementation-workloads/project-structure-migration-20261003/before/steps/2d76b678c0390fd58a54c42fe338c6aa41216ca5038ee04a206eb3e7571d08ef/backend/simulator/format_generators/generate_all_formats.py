"""Compatibility only; owner backend.nis.traces.formats.generate_all_formats."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.traces.formats.generate_all_formats')
