"""Compatibility only; owner backend.nis.knowledge.industry_rag."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.knowledge.industry_rag')
