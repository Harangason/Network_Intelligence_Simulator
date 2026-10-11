"""Compatibility only; owner backend.nis.traces.formats.mdf_writer."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.traces.formats.mdf_writer')
