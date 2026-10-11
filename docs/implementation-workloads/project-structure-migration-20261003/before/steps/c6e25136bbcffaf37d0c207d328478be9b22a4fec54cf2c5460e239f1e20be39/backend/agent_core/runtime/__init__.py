"""Shared, entry-point independent runtime contracts for engineering requests."""

from .goal_resolver import EngineeringGoal, GoalResolver, GoalType
from .service import EngineeringAssistantService
from .workload import EngineeringWorkload, WorkloadStatus

__all__ = ["EngineeringAssistantService", "EngineeringGoal", "EngineeringWorkload", "GoalResolver", "GoalType", "WorkloadStatus"]
