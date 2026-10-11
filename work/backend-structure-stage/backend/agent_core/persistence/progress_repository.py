"""Compatibility only; owner backend.nis.agent.persistence.progress_repository."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.persistence.progress_repository')
