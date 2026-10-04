"""Compatibility only; owner backend.nis.agent.proposals.proposal_store."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.proposals.proposal_store')
