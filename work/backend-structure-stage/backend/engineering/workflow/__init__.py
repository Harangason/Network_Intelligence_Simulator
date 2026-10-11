"""Compatibility only; owner backend.nis.workflow.services."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.workflow.services')
