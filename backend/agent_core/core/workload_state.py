from __future__ import annotations

from enum import StrEnum


class WorkloadStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    VALIDATING = "VALIDATING"
    INCOMPLETE = "INCOMPLETE"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    PAUSED = "PAUSED"
    CANCELED = "CANCELED"


class DependencyState(StrEnum):
    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"


TERMINAL_STATUSES = frozenset(
    {
        WorkloadStatus.COMPLETED,
        WorkloadStatus.FAILED,
        WorkloadStatus.BLOCKED,
        WorkloadStatus.CANCELED,
    }
)
