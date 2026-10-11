"""Compatibility only; owner backend.nis.engineering.structure.system_ownership."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.structure.system_ownership')
