"""Portable contracts shared by MCP, the agent and UI consumers."""
from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class Permission(StrEnum):
    READ_MODEL = "READ_MODEL"
    GENERATE_PROPOSAL = "GENERATE_PROPOSAL"
    VALIDATE = "VALIDATE"
    RUN_SIMULATION = "RUN_SIMULATION"
    ANALYZE_TRACE = "ANALYZE_TRACE"
    APPLY_APPROVED_PROPOSAL = "APPLY_APPROVED_PROPOSAL"
    DELETE_WITH_IMPACT_ANALYSIS = "DELETE_WITH_IMPACT_ANALYSIS"
    ADMIN = "ADMIN"


class ToolStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    INVALID_INPUT = "INVALID_INPUT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    CONFLICT = "CONFLICT"
    NOT_FOUND = "NOT_FOUND"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BLOCKED = "BLOCKED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool = True
    status: ToolStatus = ToolStatus.SUCCESS
    data: Any = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    time_range: dict[str, Any] | None = None
    validation_status: str = "NOT_EVALUATED"
    affected_objects: list[dict[str, str]] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    OUTDATED = "OUTDATED"


class EngineeringProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str
    proposal_type: str
    object_refs: list[dict[str, str]] = Field(default_factory=list)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str
    assumptions: list[str] = Field(default_factory=list)
    validation_result: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    status: ProposalStatus = ProposalStatus.PROPOSED
