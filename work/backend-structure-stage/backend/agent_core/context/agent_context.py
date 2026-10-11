"""Compatibility only; owner backend.nis.agent.context.agent_context."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.context.agent_context')
