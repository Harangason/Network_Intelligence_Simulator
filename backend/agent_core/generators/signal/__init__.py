"""Extension point for simulator-specific signal generators."""

from ..base import BaseGenerator

SignalGenerator = BaseGenerator

__all__ = ["SignalGenerator"]
