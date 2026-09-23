"""Engineering result contract with explicit completion and evidence."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .completion import CompletionEvaluator
from .goal_resolver import EngineeringGoal


class EngineeringAssistantResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    goal: EngineeringGoal
    workload_id: str
    status: str
    completed: bool
    summary: str = ""
    achieved_outcomes: list[str] = Field(default_factory=list)
    missing_outcomes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    capability_id: str = ""
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ResultComposer:
    def compose(self, goal: EngineeringGoal, workload: dict, events: list[dict], *, failure=None) -> EngineeringAssistantResult:
        completion = CompletionEvaluator().evaluate(goal.model_dump(mode="json"), events, failure=failure)
        result_event = next((item for item in reversed(events) if item.get("type") in {"RESULT", "ERROR"}), {})
        return EngineeringAssistantResult(goal=goal, workload_id=str(workload["workload_id"]),
            status=completion["status"], completed=completion["completed"],
            summary=str(result_event.get("text") or ""),
            achieved_outcomes=completion.get("achieved_outcomes", []),
            missing_outcomes=completion.get("missing_outcomes", []),
            evidence_refs=completion.get("evidence_refs", []),
            capability_id=str((workload.get("capability") or {}).get("capability_id") or ""),
            findings=list(result_event.get("findings") or []))
