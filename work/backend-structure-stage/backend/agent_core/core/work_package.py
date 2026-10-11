"""Compatibility only; owner backend.nis.agent.core.work_package."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.core.work_package')
