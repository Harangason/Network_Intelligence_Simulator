"""Compatibility only; owner backend.nis.agent.orchestration.workload_orchestrator."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.agent.orchestration.workload_orchestrator')
