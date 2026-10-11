"""Compatibility only; owner backend.nis.domain.core.models."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.domain.core.models')
