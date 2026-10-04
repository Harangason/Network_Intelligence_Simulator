"""Compatibility only; owner backend.nis.simulation.job_service."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module('backend.nis.simulation.job_service')
