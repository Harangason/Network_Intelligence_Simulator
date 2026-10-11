"""Compatibility only; owner backend.nis.agent.orchestration.tool_arguments."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.orchestration.tool_arguments')
