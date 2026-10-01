"""Canonical access to the nine-stage workflow structure."""

from backend.workflow import (
    WORKFLOW_LABELS,
    WORKFLOW_STATUSES,
    WORKFLOW_STAGES,
    WORKFLOW_STEPS,
    WorkflowStageDefinition,
    workflow_stage,
)

__all__ = [
    "WORKFLOW_LABELS", "WORKFLOW_STATUSES", "WORKFLOW_STAGES",
    "WORKFLOW_STEPS", "WorkflowStageDefinition", "workflow_stage",
]
