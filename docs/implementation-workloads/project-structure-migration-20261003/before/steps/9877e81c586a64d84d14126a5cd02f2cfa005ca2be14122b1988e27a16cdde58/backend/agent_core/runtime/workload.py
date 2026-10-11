"""Durable engineering-workload contracts independent from any one UI."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .goal_resolver import EngineeringGoal


class WorkloadStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    WAITING_FOR_ENGINEERING_DECISION = "WAITING_FOR_ENGINEERING_DECISION"
    IN_PROGRESS = "IN_PROGRESS"
    VALIDATING = "VALIDATING"
    REPAIRING = "REPAIRING"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED_WITH_EXPLICIT_CAUSE = "BLOCKED_WITH_EXPLICIT_CAUSE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NOT_SUPPORTED_WITH_CAPABILITY_GAP = "NOT_SUPPORTED_WITH_CAPABILITY_GAP"


class EngineeringWorkload(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    workload_id: str
    goal: EngineeringGoal
    project_id: str
    owner_run_id: str = ""
    status: WorkloadStatus = WorkloadStatus.RECEIVED
    plan: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    capability: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list, max_length=500)
    result: dict[str, Any] | None = None
    failure: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkloadManager:
    """Creates and transitions workload snapshots through one durable sink."""

    def __init__(self, persist):
        self.persist = persist

    def save(self, workload: EngineeringWorkload) -> EngineeringWorkload:
        workload.updated_at = datetime.now(timezone.utc).isoformat()
        self.persist(workload.model_dump(mode="json"))
        return workload
