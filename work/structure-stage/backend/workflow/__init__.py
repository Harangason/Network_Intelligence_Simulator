"""Canonical structure for the nine-stage NIS engineering workflow."""

from backend.workflow.definition import WORKFLOW_LABELS, WORKFLOW_STATUSES, WORKFLOW_STAGES, WORKFLOW_STEPS, WorkflowStageDefinition, workflow_stage

__all__ = [
    "WORKFLOW_LABELS",
    "WORKFLOW_STATUSES",
    "WORKFLOW_STAGES",
    "WORKFLOW_STEPS",
    "WorkflowStageDefinition",
    "workflow_stage",
]
