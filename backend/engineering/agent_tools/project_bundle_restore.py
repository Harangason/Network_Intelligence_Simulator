"""Compatibility only; owner backend.nis.agent.tools.project_bundle_restore."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.tools.project_bundle_restore')
