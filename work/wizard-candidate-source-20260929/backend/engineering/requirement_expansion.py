"""Deterministic Requirement Expansion engine public facade.

Kept for backwards-compatible imports from the workload handler and API layer.
"""

from .requirement_expansion_modules.constants import ENGINE_VERSION, WORKFLOW_STATUSES
from .requirement_expansion_modules.engine import expand_requirement

__all__ = [
    "ENGINE_VERSION",
    "WORKFLOW_STATUSES",
    "expand_requirement",
]
