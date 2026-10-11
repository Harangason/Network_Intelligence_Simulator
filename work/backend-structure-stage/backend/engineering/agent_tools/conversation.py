"""Compatibility only; owner backend.nis.agent.tools.conversation."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.tools.conversation')
