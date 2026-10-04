"""Compatibility only; owner backend.nis.agent.validation.completion_validator."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.validation.completion_validator')
