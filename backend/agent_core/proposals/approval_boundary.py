"""Compatibility only; owner backend.nis.agent.proposals.approval_boundary."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.proposals.approval_boundary')
