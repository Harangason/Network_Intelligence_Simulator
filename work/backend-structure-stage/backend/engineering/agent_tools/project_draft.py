"""Compatibility only; owner backend.nis.agent.tools.project_draft."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.tools.project_draft')
