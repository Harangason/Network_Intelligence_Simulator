"""Compatibility only; owner backend.nis.infrastructure.storage.trace_storage."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.infrastructure.storage.trace_storage')
