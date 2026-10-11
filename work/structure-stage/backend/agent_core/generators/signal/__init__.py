"""Extension point for simulator-specific signal generators."""

from backend.agent_core.generators.base import BaseGenerator

SignalGenerator = BaseGenerator

__all__ = ["SignalGenerator"]
