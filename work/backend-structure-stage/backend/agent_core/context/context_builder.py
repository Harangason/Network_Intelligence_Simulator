"""Compatibility only; owner backend.nis.agent.context.context_builder."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.context.context_builder')
