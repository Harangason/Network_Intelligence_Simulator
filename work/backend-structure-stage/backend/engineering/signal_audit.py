"""Compatibility only; owner backend.nis.engineering.signals.signal_audit."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.signals.signal_audit')
