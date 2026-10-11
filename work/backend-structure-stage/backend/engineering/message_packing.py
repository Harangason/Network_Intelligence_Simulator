"""Compatibility only; owner backend.nis.engineering.signals.message_packing."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.signals.message_packing')
