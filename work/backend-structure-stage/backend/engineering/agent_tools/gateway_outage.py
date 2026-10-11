"""Compatibility only; owner backend.nis.agent.tools.gateway_outage."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.tools.gateway_outage')
