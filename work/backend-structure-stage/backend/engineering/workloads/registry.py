"""Compatibility only; owner backend.nis.engineering.workloads.registry."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.workloads.registry')
