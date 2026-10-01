"""Single structural definition of the NIS project workflow.

The established engineering workflow still executes through
``backend.engineering.workflow``.  This module owns stable stage identity,
ordering, dependencies and source provenance so that packages, documentation
and user interfaces can refer to the same structure without moving business
behaviour between programming languages.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowStageDefinition:
    """Structural ownership and provenance for one workflow stage."""

    id: str
    position: int
    label: str
    route: str
    backend_sources: tuple[str, ...]
    frontend_feature: str
    consumes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()


WORKFLOW_STAGES = (
    WorkflowStageDefinition(
        "engineering_model", 1, "Engineering-Modell", "/studio/engineering",
        ("backend.engineering.models", "backend.engineering.repository", "backend.engineering.api"),
        "frontend/src/features/workflow/stage_01_engineering_model",
        produces=("canonical_engineering_model",),
    ),
    WorkflowStageDefinition(
        "routing", 2, "Routing-Tabelle", "/studio/routing",
        ("backend.engineering.routing", "backend.engineering.confirmed_routes"),
        "frontend/src/features/workflow/stage_02_routing",
        consumes=("engineering_model",), produces=("routing_table",),
    ),
    WorkflowStageDefinition(
        "network_editor", 3, "Netzwerk-Editor", "/studio?mode=network",
        ("backend.engineering.network_scene", "backend.engineering.topology_sync", "backend.engineering.physical_segments"),
        "frontend/src/features/workflow/stage_03_network_editor",
        consumes=("engineering_model", "routing"), produces=("physical_topology",),
    ),
    WorkflowStageDefinition(
        "parameters", 4, "Parameter", "/studio?mode=parameters",
        ("backend.engineering.bus_settings", "backend.engineering.physical_ports"),
        "frontend/src/features/workflow/stage_04_parameters",
        consumes=("engineering_model", "routing", "network_editor"), produces=("technology_parameters",),
    ),
    WorkflowStageDefinition(
        "capacity_timing", 5, "Capacity & Timing", "/studio/capacity",
        ("backend.engineering.capacity",),
        "frontend/src/features/workflow/stage_05_capacity_timing",
        consumes=("routing", "network_editor", "parameters"), produces=("capacity_assessment",),
    ),
    WorkflowStageDefinition(
        "validation", 6, "Validation / Preflight", "/studio/validation",
        ("backend.engineering.capacity.service", "backend.engineering.agent_tools.validation"),
        "frontend/src/features/workflow/stage_06_validation",
        consumes=("engineering_model", "routing", "network_editor", "parameters", "capacity_timing"),
        produces=("preflight_assessment",),
    ),
    WorkflowStageDefinition(
        "simulation", 7, "Simulation", "/studio/simulation",
        ("backend.engineering.simulation", "backend.app.simulation_service", "backend.simulator"),
        "frontend/src/features/workflow/stage_07_simulation",
        consumes=("validation",), produces=("simulation_snapshot", "simulation_trace"),
    ),
    WorkflowStageDefinition(
        "results_analysis", 8, "Results / Analysis", "/studio/results",
        ("backend.app.runtime_analysis", "backend.app.trace_service"),
        "frontend/src/features/workflow/stage_08_results_analysis",
        consumes=("simulation",), produces=("analysis_result",),
    ),
    WorkflowStageDefinition(
        "data_science_intelligence", 9, "Data Science & Intelligence", "/studio/intelligence",
        ("backend.engineering.intelligence", "backend.intelligence"),
        "frontend/src/features/workflow/stage_09_intelligence",
        consumes=("engineering_model", "routing", "capacity_timing", "validation", "simulation", "results_analysis"),
        produces=("intelligence_assessment",),
    ),
)

WORKFLOW_STEPS = tuple(stage.id for stage in WORKFLOW_STAGES)
WORKFLOW_LABELS = {stage.id: stage.label for stage in WORKFLOW_STAGES}
WORKFLOW_STATUSES = (
    "EMPTY",
    "IN_PROGRESS",
    "COMPLETE",
    "WARNING",
    "ERROR",
    "APPROVED",
    "OUTDATED",
)


def workflow_stage(stage_id: str) -> WorkflowStageDefinition:
    """Return structural metadata for one known stage."""

    try:
        return next(stage for stage in WORKFLOW_STAGES if stage.id == stage_id)
    except StopIteration as exc:
        raise ValueError(f"Unbekannter Workflow-Schritt: {stage_id!r}") from exc
