"""Compatibility only; owner backend.nis.interfaces.http.engineering."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.interfaces.http.engineering')
