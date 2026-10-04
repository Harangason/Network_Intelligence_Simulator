"""Compatibility only; owner backend.nis.engineering.projects.project_context."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.projects.project_context')
