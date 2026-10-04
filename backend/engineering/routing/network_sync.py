"""Compatibility only; owner backend.nis.engineering.routing.network_sync."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.routing.network_sync')
