"""Compatibility only; owner backend.nis.workflow.definition."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.workflow.definition')
