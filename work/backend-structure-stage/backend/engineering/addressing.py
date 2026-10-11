"""Compatibility only; owner backend.nis.domain.addressing."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.domain.addressing')
