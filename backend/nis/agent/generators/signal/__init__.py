"""Extension point for simulator-specific signal generators."""

from backend.nis.agent.generators.base import BaseGenerator

SignalGenerator = BaseGenerator

__all__ = ["SignalGenerator"]
