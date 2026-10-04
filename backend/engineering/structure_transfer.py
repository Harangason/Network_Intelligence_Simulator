"""Compatibility only; owner backend.nis.engineering.structure.structure_transfer."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.structure.structure_transfer')
