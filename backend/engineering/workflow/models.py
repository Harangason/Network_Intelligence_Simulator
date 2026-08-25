"""Pure workflow state transitions shared by the API and tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

WORKFLOW_STEPS = (
    "engineering_model",
    "routing",
    "network_editor",
    "parameters",
    "capacity_timing",
    "validation",
    "simulation",
    "results_analysis",
    "data_science_intelligence",
)

WORKFLOW_LABELS = {
    "engineering_model": "Engineering-Modell",
    "routing": "Routing-Tabelle",
    "network_editor": "Netzwerk-Editor",
    "parameters": "Parameter",
    "capacity_timing": "Capacity & Timing",
    "validation": "Validation / Preflight",
    "simulation": "Simulation",
    "results_analysis": "Results / Analysis",
    "data_science_intelligence": "Data Science & Intelligence",
}

WORKFLOW_STATUSES = (
    "EMPTY",
    "IN_PROGRESS",
    "COMPLETE",
    "WARNING",
    "ERROR",
    "APPROVED",
    "OUTDATED",
)


def default_versions() -> dict[str, int]:
    return {step: 0 for step in WORKFLOW_STEPS}


def default_statuses() -> dict[str, str]:
    return {step: "EMPTY" for step in WORKFLOW_STEPS}


def normalize_step(step: str) -> str:
    if step not in WORKFLOW_STEPS:
        raise ValueError(f"Unbekannter Workflow-Schritt: {step!r}")
    return step


def transition_state(
    state: dict[str, Any],
    step: str,
    reason: str,
    *,
    status: str = "COMPLETE",
) -> dict[str, Any]:
    """Increment one source version and mark every dependent result stale."""
    normalize_step(step)
    if status not in WORKFLOW_STATUSES:
        raise ValueError(f"Unbekannter Workflow-Status: {status!r}")
    next_state = deepcopy(state)
    versions = {**default_versions(), **next_state.get("versions", {})}
    statuses = {**default_statuses(), **next_state.get("statuses", {})}
    stale_reasons = dict(next_state.get("stale_reasons", {}))
    versions[step] = int(versions.get(step, 0)) + 1
    statuses[step] = status
    stale_reasons.pop(step, None)

    changed_index = WORKFLOW_STEPS.index(step)
    for dependent in WORKFLOW_STEPS[changed_index + 1 :]:
        if statuses.get(dependent) != "EMPTY":
            statuses[dependent] = "OUTDATED"
            stale_reasons[dependent] = reason

    next_state.update(
        {
            "active_step": step,
            "versions": versions,
            "statuses": statuses,
            "stale_reasons": stale_reasons,
        }
    )
    return next_state


def set_step_status(
    state: dict[str, Any], step: str, status: str, reason: str | None = None
) -> dict[str, Any]:
    normalize_step(step)
    if status not in WORKFLOW_STATUSES:
        raise ValueError(f"Unbekannter Workflow-Status: {status!r}")
    next_state = deepcopy(state)
    next_state["statuses"] = {**default_statuses(), **next_state.get("statuses", {})}
    next_state["stale_reasons"] = dict(next_state.get("stale_reasons", {}))
    next_state["statuses"][step] = status
    if reason:
        next_state["stale_reasons"][step] = reason
    elif status != "OUTDATED":
        next_state["stale_reasons"].pop(step, None)
    return next_state
