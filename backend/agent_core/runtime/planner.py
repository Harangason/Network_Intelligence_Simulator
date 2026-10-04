"""Compatibility alias for executable agent runtime."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.runtime.planner')
