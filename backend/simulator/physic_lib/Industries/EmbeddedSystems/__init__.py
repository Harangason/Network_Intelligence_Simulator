"""Compatibility only; owner backend.nis.industries.embedded_systems.templates."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.industries.embedded_systems.templates')
