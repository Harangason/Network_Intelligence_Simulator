"""Compatibility only; owner backend.nis.simulation.industry_knowledge."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.industry_knowledge')
