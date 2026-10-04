"""Compatibility only; owner backend.nis.engineering.communication.device_communication."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.engineering.communication.device_communication')
