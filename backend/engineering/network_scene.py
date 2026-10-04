"""Compatibility only; owner backend.nis.engineering.network.network_scene."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.network.network_scene')
