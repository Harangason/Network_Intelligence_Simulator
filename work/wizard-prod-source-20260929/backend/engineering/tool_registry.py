"""Engineering tool capability registry.

This registry is descriptive: it tells the agent and UI which capabilities
exist, what they need, and where human approval is mandatory. Execution remains
on the existing validated API routes and agent tools.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from backend.agent_core.registry import ToolRegistry
except ModuleNotFoundError:  # Tests execute with backend as the import root.
    from agent_core.registry import ToolRegistry


@dataclass(frozen=True)
class EngineeringToolDefinition:
    id: str
    name: str
    category: str
    description: str
    workflow_step: str
    capabilities: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    supported_industries: tuple[str, ...] = ("all",)
    supported_formats: tuple[str, ...] = ()
    requires_approval: bool = False
    approval_scope: str = "none"
    status: str = "available"
    risk_level: str = "low"
    execution_endpoint: str | None = None
    ai_usage: str = "assist"
    safeguards: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _schema(required: tuple[str, ...] = (), **properties: Any) -> dict[str, Any]:
    return {"type": "object", "required": list(required), "properties": properties}


_FORMATS = (
    "dbc", "csv", "xlsx", "json", "routing-json", "arxml", "axml", "fibex",
    "ldf", "eds", "kcd", "sym", "blf", "asc", "trc", "mdf", "mf4",
    "pcap", "pcapng", "xml", "yaml",
)

_INDUSTRIES = (
    "automotive", "industrial_automation", "embedded_systems", "aerospace_defense",
    "rail", "marine", "building_automation", "energy", "robotics_ros",
    "generic_networking",
)


_DEFINITIONS: tuple[EngineeringToolDefinition, ...] = (
    EngineeringToolDefinition(
        id="import.intelligent",
        name="Intelligenter Importer",
        category="import",
        workflow_step="engineering_model",
        description="Erkennt Engineering-, Netzwerk-, Trace- und Industrieformate und erzeugt einen pruefbaren Importplan.",
        capabilities=("format_detection", "schema_mapping", "device_extraction", "signal_extraction"),
        input_schema=_schema(file={"type": "binary"}, industry={"type": "string"}),
        output_schema=_schema(plan={"type": "EngineeringImportPlan"}, warnings={"type": "array"}),
        supported_industries=_INDUSTRIES,
        supported_formats=_FORMATS,
        requires_approval=True,
        approval_scope="before_commit",
        execution_endpoint="/imports/preview",
        ai_usage="assist_and_explain",
        safeguards=("preview_only_until_commit", "source_trace_required"),
    ),
    EngineeringToolDefinition(
        id="generate.engineering_model",
        name="Engineering-Modell erzeugen",
        category="generation",
        workflow_step="engineering_model",
        description="Erzeugt Hardware, Funktionen, Interfaces, Nachrichten und Signale aus einer freigegebenen Spezifikation.",
        capabilities=("model_generation", "chain_completion", "scope_gap_documentation"),
        input_schema=_schema(("specification",), specification={"type": "string"}, target_counts={"type": "object"}),
        output_schema=_schema(objects={"type": "array"}, missing={"type": "array"}),
        supported_industries=_INDUSTRIES,
        requires_approval=True,
        approval_scope="before_apply",
        execution_endpoint="/workloads",
        ai_usage="generate_with_review_gate",
        safeguards=("bounded_retry", "missing_items_are_documented", "no_infinite_loop"),
    ),
    EngineeringToolDefinition(
        id="expand.requirement",
        name="Anforderung mit Reviewstruktur expandieren",
        category="generation",
        workflow_step="engineering_model",
        description="Leitet aus einer natuerlichsprachlichen Anforderung ein vollstaendiges, deterministisch berechnetes Proposal mit Ambiguitäten, Annahmen, Funktionen, Sensorik, Signals, Nachrichten, Routing und Review-Entscheidungen ab.",
        capabilities=("requirement_understanding", "ambiguous_input_detection", "assumption_generation", "deterministic_calculation", "repair_loop", "human_review_gate"),
        input_schema=_schema(
            ("specification", "workload_type"),
            specification={"type": "string"},
            workload_type={"type": "string", "enum": ["REQUIREMENT_EXPANSION"]},
            domain={"type": "string"},
        ),
        output_schema=_schema(objects={"type": "array"}, proposal_status={"type": "string"}, open_decisions={"type": "array"}, completion={"type": "object"}),
        supported_industries=_INDUSTRIES,
        requires_approval=True,
        approval_scope="before_apply",
        execution_endpoint="/workloads",
        ai_usage="generate_with_review_gate",
        safeguards=("explicit_human_review", "no_direct_core_write", "open_decisions_visible", "capacity_timing_visible", "message_packing_visible"),
    ),
    EngineeringToolDefinition(
        id="suggest.network_architecture",
        name="Netzarchitektur vorschlagen",
        category="architecture",
        workflow_step="routing",
        description="Bewertet EVA, ECU-vermittelt, Gateway-direkt oder Hybridarchitekturen mit explizitem Review-Gate.",
        capabilities=("architecture_selection", "hybrid_planning", "approval_gate"),
        input_schema=_schema(devices={"type": "array"}, technologies={"type": "array"}),
        output_schema=_schema(variant={"type": "string"}, rationale={"type": "array"}),
        supported_industries=_INDUSTRIES,
        requires_approval=True,
        approval_scope="before_apply",
        ai_usage="recommend_with_explicit_approval",
        safeguards=("mandatory_human_release",),
    ),
    EngineeringToolDefinition(
        id="generate.system_clusters",
        name="Systemrahmen bilden",
        category="architecture",
        workflow_step="network_editor",
        description="Fasst fachlich zusammenhaengende ECUs, Sensoren und Aktoren in Systemrahmen zusammen.",
        capabilities=("system_clustering", "bidirectional_dependency_grouping", "layout_grouping"),
        input_schema=_schema(hardware={"type": "array"}, topology={"type": "object"}),
        output_schema=_schema(clusters={"type": "array"}, assignments={"type": "array"}),
        supported_industries=_INDUSTRIES,
        requires_approval=True,
        approval_scope="before_apply",
        execution_endpoint="/structure/evaluate",
        ai_usage="assist_and_explain",
        safeguards=("preserve_existing_assignments", "human_review_for_merges"),
    ),
    EngineeringToolDefinition(
        id="sync.routing_topology",
        name="Routing und Topologie synchronisieren",
        category="topology",
        workflow_step="network_editor",
        description="Verbindet Routingpfade mit realen Ports, Interfaces, Netzen und Gateway-Segmenten.",
        capabilities=("port_mapping", "network_segment_mapping", "route_sync"),
        input_schema=_schema(topology={"type": "object"}),
        output_schema=_schema(nodes={"type": "array"}, edges={"type": "array"}),
        supported_industries=_INDUSTRIES,
        execution_endpoint="/topology/sync",
        ai_usage="assist",
        safeguards=("layout_changes_do_not_invalidate_model",),
    ),
    EngineeringToolDefinition(
        id="validate.signal_sizing",
        name="Signalgroessen pruefen",
        category="validation",
        workflow_step="capacity_timing",
        description="Prueft Sender, Teilnehmer, Systemrahmen, Signalanzahl und auffaellige Bitlaengen.",
        capabilities=("sender_receiver_audit", "system_frame_context", "bit_length_check", "payload_efficiency"),
        input_schema=_schema(capacity_snapshot={"type": "object"}),
        output_schema=_schema(findings={"type": "array"}, recommendations={"type": "array"}),
        supported_industries=_INDUSTRIES,
        execution_endpoint="/capacity",
        ai_usage="diagnose_and_explain",
        safeguards=("findings_visible_even_when_blocked",),
    ),
    EngineeringToolDefinition(
        id="analyze.capacity_timing",
        name="Capacity & Timing berechnen",
        category="analysis",
        workflow_step="capacity_timing",
        description="Berechnet Buslast, Peak/Burst, Reserve, Queueing, Gateway-Last und End-to-End-Latenz.",
        capabilities=("busload_calculation", "timing_analysis", "queueing", "gateway_load"),
        input_schema=_schema(overrides={"type": "object"}),
        output_schema=_schema(snapshot={"type": "CapacitySnapshot"}, findings={"type": "array"}),
        supported_industries=_INDUSTRIES,
        execution_endpoint="/capacity/calculate",
        ai_usage="deterministic_calculation",
        safeguards=("versioned_snapshot", "outdated_detection"),
    ),
    EngineeringToolDefinition(
        id="suggest.network_distribution",
        name="Netzlast verteilen",
        category="optimization",
        workflow_step="data_science_intelligence",
        description="Schlaegt zusaetzliche Netzsegmente und eine fachlich gruppierte Lastverteilung vor.",
        capabilities=("overload_diagnosis", "segment_split", "gateway_port_planning", "system_cluster_preservation"),
        input_schema=_schema(capacity={"type": "object"}, topology={"type": "object"}, hardware={"type": "array"}),
        output_schema=_schema(proposal={"type": "OptimizationProposal"}, expected_impact={"type": "object"}),
        supported_industries=_INDUSTRIES,
        requires_approval=True,
        approval_scope="before_apply",
        execution_endpoint="/capacity/optimize",
        ai_usage="recommend_with_review_gate",
        safeguards=("never_apply_autonomously", "keep_related_systems_together"),
    ),
    EngineeringToolDefinition(
        id="validate.preflight",
        name="Preflight validieren",
        category="validation",
        workflow_step="validation",
        description="Prueft blockierende Modell-, Routing-, Parameter-, Capacity- und Simulationsvoraussetzungen.",
        capabilities=("blocking_error_detection", "warning_documentation", "simulation_gate"),
        input_schema=_schema(),
        output_schema=_schema(snapshot={"type": "PreflightSnapshot"}, ready_for_simulation={"type": "boolean"}),
        supported_industries=_INDUSTRIES,
        execution_endpoint="/preflight",
        ai_usage="deterministic_validation",
        safeguards=("simulation_requires_green_preflight",),
    ),
    EngineeringToolDefinition(
        id="simulate.trace_run",
        name="Trace-Simulation starten",
        category="simulation",
        workflow_step="simulation",
        description="Erzeugt einen SimulationSnapshot und startet einen versionierten Simulatorlauf.",
        capabilities=("snapshot_creation", "trace_generation", "runtime_metrics"),
        input_schema=_schema(configuration={"type": "object"}),
        output_schema=_schema(job={"type": "SimulationJob"}, artifacts={"type": "array"}),
        supported_industries=_INDUSTRIES,
        supported_formats=("jsonl", "csv", "blf", "asc", "trc", "pcap", "pcapng", "mdf", "mf4"),
        execution_endpoint="/workflow/simulation-snapshots",
        ai_usage="execute_after_validation",
        safeguards=("requires_current_preflight", "job_registry_compacted"),
    ),
    EngineeringToolDefinition(
        id="assess.intelligence",
        name="Data Science & Intelligence bewerten",
        category="intelligence",
        workflow_step="data_science_intelligence",
        description="Erzeugt Reifegrad, Issues, Anomalien, Ursachen, Korrelationen und Optimierungsvorschlaege.",
        capabilities=("maturity_assessment", "issue_detection", "root_cause_analysis", "proposal_generation"),
        input_schema=_schema(),
        output_schema=_schema(assessment={"type": "IntelligenceAssessment"}, proposals={"type": "array"}),
        supported_industries=_INDUSTRIES,
        execution_endpoint="/intelligence/assess",
        ai_usage="deterministic_plus_ai_assisted_recommendations",
        safeguards=("visible_findings_when_blocked", "proposals_require_review"),
    ),
    EngineeringToolDefinition(
        id="export.trace_artifacts",
        name="Trace-Artefakte exportieren",
        category="export",
        workflow_step="results_analysis",
        description="Stellt universelle und native Trace-/Messdatenformate fuer weitere Toolketten bereit.",
        capabilities=("artifact_download", "native_trace_formats", "analysis_handoff"),
        input_schema=_schema(job_id={"type": "string"}, format={"type": "string"}),
        output_schema=_schema(artifact={"type": "file"}),
        supported_industries=_INDUSTRIES,
        supported_formats=("jsonl", "csv", "json", "xml", "yaml", "blf", "asc", "trc", "pcap", "pcapng", "mdf", "mf4"),
        ai_usage="assist",
        safeguards=("artifacts_reference_jobs",),
    ),
)


def _tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for definition in _DEFINITIONS:
        registry.register(definition.id, definition)
    return registry


ENGINEERING_TOOL_REGISTRY = _tool_registry()


def list_engineering_tools(
    *,
    category: str | None = None,
    industry: str | None = None,
    status: str | None = None,
    approval_required: bool | None = None,
    workflow_step: str | None = None,
) -> list[dict[str, Any]]:
    category_key = (category or "").strip().lower()
    industry_key = (industry or "").strip().lower()
    status_key = (status or "").strip().lower()
    workflow_key = (workflow_step or "").strip().lower()

    def matches(tool: EngineeringToolDefinition) -> bool:
        if category_key and tool.category.lower() != category_key:
            return False
        if status_key and tool.status.lower() != status_key:
            return False
        if workflow_key and tool.workflow_step.lower() != workflow_key:
            return False
        if approval_required is not None and tool.requires_approval is not approval_required:
            return False
        if industry_key and "all" not in tool.supported_industries and industry_key not in tool.supported_industries:
            return False
        return True

    return [tool.as_dict() for tool in ENGINEERING_TOOL_REGISTRY.filter(matches)]


def get_engineering_tool(tool_id: str) -> dict[str, Any]:
    return ENGINEERING_TOOL_REGISTRY.get(tool_id).as_dict()
