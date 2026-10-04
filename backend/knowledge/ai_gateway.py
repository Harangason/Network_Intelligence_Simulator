"""Compatibility only; owner backend.nis.knowledge.ai_gateway."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.ai_gateway')
