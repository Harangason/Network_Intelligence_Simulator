from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProposalStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"


@dataclass(slots=True)
class Proposal:
    proposal_id: str
    workload_id: str
    objects: list[dict[str, Any]]
    status: ProposalStatus = ProposalStatus.DRAFT
    generated_by: str = "agent_core"
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    approved_by: str | None = None
