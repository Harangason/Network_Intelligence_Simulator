"""Simulation runtime, signal behaviour, faults and traces."""

from ..models import Capability

CAPABILITY = Capability(
    "simulation", "Simulation",
    ("backend.simulator", "backend.engineering.simulation", "backend.app.simulation_service"),
    "Model-based execution, communication events, signals, faults and trace formats.",
)
__all__ = ["CAPABILITY"]
