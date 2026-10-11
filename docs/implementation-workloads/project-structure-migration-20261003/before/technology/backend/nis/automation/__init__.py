"""Agent, wizard, proposal and workload orchestration."""

from ..models import Capability

CAPABILITY = Capability(
    "automation", "Automation",
    (
        "backend.agent_core", "backend.engineering.agent_tools",
        "backend.engineering.goal_execution", "backend.engineering.workloads",
        "backend.engineering.requirement_expansion_modules",
    ),
    "Agent execution, wizard commands, proposals, workloads and requirement expansion.",
)
__all__ = ["CAPABILITY"]
