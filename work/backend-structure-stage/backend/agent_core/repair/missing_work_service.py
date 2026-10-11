"""Compatibility only; owner backend.nis.agent.repair.missing_work_service."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.repair.missing_work_service')
