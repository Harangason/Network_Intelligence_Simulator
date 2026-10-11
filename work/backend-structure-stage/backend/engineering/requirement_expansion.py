"""Compatibility only; owner backend.nis.engineering.requirements.requirement_expansion."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.requirements.requirement_expansion')
