"""Compatibility only; owner backend.nis.communication.technologies.ethernet.transport."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.communication.technologies.ethernet.transport')
