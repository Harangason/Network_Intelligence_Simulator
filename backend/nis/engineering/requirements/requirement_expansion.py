"""Deterministic Requirement Expansion engine public facade.

Kept for backwards-compatible imports from the workload handler and API layer.
"""

from backend.nis.engineering.requirement_expansion_modules.constants import ENGINE_VERSION
from backend.nis.engineering.requirement_expansion_modules.constants import WORKFLOW_STATUSES
from backend.nis.engineering.requirement_expansion_modules.engine import expand_requirement

__all__ = [
    "ENGINE_VERSION",
    "WORKFLOW_STATUSES",
    "expand_requirement",
]
