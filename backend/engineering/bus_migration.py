"""Compatibility only; owner backend.nis.engineering.network.bus_migration."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.network.bus_migration')
