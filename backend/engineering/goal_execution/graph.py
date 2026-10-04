"""Compatibility only; owner backend.nis.engineering.goal_execution.graph."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.goal_execution.graph')
