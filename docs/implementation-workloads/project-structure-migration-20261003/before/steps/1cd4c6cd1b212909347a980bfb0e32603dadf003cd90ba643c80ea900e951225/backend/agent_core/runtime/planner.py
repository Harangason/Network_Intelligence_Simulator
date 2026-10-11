"""Build a bounded, auditable execution plan from registered capabilities."""
from __future__ import annotations

from .goal_resolver import EngineeringGoal


class EngineeringPlanner:
    """Plan through existing MCP adapters; it never fabricates Core operations."""

    def plan(self, goal: EngineeringGoal, capability: dict) -> list[dict]:
        tools = list(capability.get("available_tools") or [])
        action = "Execute the registered engineering capability" if tools else "Capability gap"
        return [
            {"step_id": "context", "action": "Read project context and selected model objects",
             "status": "PLANNED", "evidence_required": ["project_id", "selected_objects", "model_revision"]},
            {"step_id": "engineering_action", "action": action, "status": "PLANNED",
             "candidate_adapters": tools, "required_outcomes": list(goal.required_outcomes)},
            {"step_id": "domain_validation", "action": "Run the relevant registered validator or calculation",
             "status": "PLANNED", "evidence_required": list(goal.required_outcomes)},
            {"step_id": "completion", "action": "Evaluate requested outcomes against stored Core evidence",
             "status": "PLANNED", "evidence_required": ["achieved_outcomes", "missing_outcomes", "evidence_refs"]},
        ]
