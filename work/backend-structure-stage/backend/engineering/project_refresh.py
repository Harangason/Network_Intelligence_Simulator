"""Compatibility only; owner backend.nis.engineering.projects.project_refresh."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.projects.project_refresh')
