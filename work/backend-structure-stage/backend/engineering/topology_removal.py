"""Compatibility only; owner backend.nis.engineering.network.topology_removal."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.network.topology_removal')
