"""Simulation runtime, signal behaviour, faults and traces."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "simulation", "Simulation",
    ("backend.nis.simulation", "backend.nis.engineering.simulation", "backend.nis.simulation.service"),
    "Model-based execution, communication events, signals, faults and trace formats.",
)
__all__ = ["CAPABILITY"]
