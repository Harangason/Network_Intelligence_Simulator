"""Compatibility only; owner backend.nis.engineering.network.physical_ports."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.network.physical_ports')
