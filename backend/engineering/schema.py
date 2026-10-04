"""Compatibility only; owner backend.nis.infrastructure.persistence.schema."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.infrastructure.persistence.schema')
