"""Compatibility only; owner backend.nis.infrastructure.storage.saved_storage."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.infrastructure.storage.saved_storage')
