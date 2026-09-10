"""Consumer-independent context carried by the engineering agent, never authority."""
from __future__ import annotations

from typing import Any
from backend.agent_core.context.limits import MAX_REQUIREMENT_LENGTH
from pydantic import BaseModel, ConfigDict, Field


class DocumentSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=180)
    size: int = Field(gt=0, le=5 * 1024 * 1024)
    format: str = Field(min_length=1, max_length=10)
    text: str = Field(min_length=1, max_length=16_000)
    truncated: bool


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active_project_id: str = Field(min_length=1, max_length=200)
    active_workflow: str = "engineering"
    active_view: str = "model"
    selected_object_refs: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    current_requirement: str = Field(default="", max_length=MAX_REQUIREMENT_LENGTH)
    current_workload: str | None = None
    project_domain: str = "automotive"
    assumptions: list[str] = Field(default_factory=list)
    unresolved_findings: list[dict[str, Any]] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    answered_questions: dict[str, Any] = Field(default_factory=dict)
    active_proposal: str | None = None
    document_sources: list[DocumentSource] = Field(default_factory=list, max_length=4)
