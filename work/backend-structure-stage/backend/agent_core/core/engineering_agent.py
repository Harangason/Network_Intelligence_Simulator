"""Compatibility only; owner backend.nis.agent.core.engineering_agent."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.core.engineering_agent')
