"""Compatibility only; owner backend.nis.engineering.routing.models."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.routing.models')
