"""Compatibility only; owner backend.nis.agent.orchestration.tool_selection."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.orchestration.tool_selection')
