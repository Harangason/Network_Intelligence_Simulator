"""Agent, wizard, proposal and workload orchestration."""

from backend.nis.models import Capability

CAPABILITY = Capability(
    "automation", "Automation",
    (
        "backend.nis.agent", "backend.nis.agent.tools",
        "backend.nis.engineering.goal_execution", "backend.nis.engineering.workloads",
        "backend.nis.engineering.requirement_expansion_modules",
    ),
    "Agent execution, wizard commands, proposals, workloads and requirement expansion.",
)
__all__ = ["CAPABILITY"]
