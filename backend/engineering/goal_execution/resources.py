"""Compatibility only; owner backend.nis.engineering.goal_execution.resources."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.goal_execution.resources')
