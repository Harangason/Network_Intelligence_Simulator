"""Compatibility only; owner backend.nis.engineering.capacity.calculators."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.capacity.calculators')
