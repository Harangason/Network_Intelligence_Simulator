"""Compatibility only; owner backend.nis.engineering.communication.communication_restore."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.communication.communication_restore')
