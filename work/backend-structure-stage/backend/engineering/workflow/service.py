"""Compatibility only; owner backend.nis.workflow.services.service."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.workflow.services.service')
