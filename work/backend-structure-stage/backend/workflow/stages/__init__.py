"""Compatibility only; owner backend.nis.workflow.stages."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.workflow.stages')
