"""Canonical structure for the nine-stage NIS engineering workflow."""

from backend.nis.workflow.definition import WORKFLOW_LABELS
from backend.nis.workflow.definition import WORKFLOW_STATUSES
from backend.nis.workflow.definition import WORKFLOW_STAGES
from backend.nis.workflow.definition import WORKFLOW_STEPS
from backend.nis.workflow.definition import WorkflowStageDefinition
from backend.nis.workflow.definition import workflow_stage

__all__ = [
    "WORKFLOW_LABELS",
    "WORKFLOW_STATUSES",
    "WORKFLOW_STAGES",
    "WORKFLOW_STEPS",
    "WorkflowStageDefinition",
    "workflow_stage",
]
