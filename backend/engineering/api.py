"""REST-Schnittstellen für das kanonische Engineering-Modell.

Dieses Blueprint stellt ausschließlich CRUD- und Versionierungs-Endpunkte für
Engineering-Objekte (HardwareNode, Function, Interface, Message, Signal),
deren Relations sowie kontrollierte Knowledge-Abfragen bereit. Simulation und
Agent bleiben getrennt; Retrieval liest ausschließlich die Source of Truth.
"""

from __future__ import annotations

import logging

import psycopg
from flask import Blueprint, Response, g, jsonify, request
from psycopg_pool import PoolTimeout

from .models import DEVICE_TYPES, EngineeringValidationError, INTERFACE_TYPES, MESSAGE_DIRECTIONS
from .db import get_connection
from .proposals import (
    approve_all_valid_proposals,
    approve_proposal,
    create_proposal,
    get_proposal,
    list_proposals,
    reject_proposal,
    update_proposal,
    validate_proposal,
)
from .relations import create_relation, delete_relation, get_relation, list_relations
from .repository import (
    ENTITY_SPECS,
    NotFoundError,
    create_object,
    delete_object,
    get_object,
    list_objects,
    list_versions,
    update_object,
)
from .topology_sync import sync_topology
from .importer import commit_import, preview_import
from .knowledge import CanonicalKnowledgeService
from .routing.config_builder import CommunicationConfigBuilder
from .routing.generation import RoutingGenerationService
from .routing.network_sync import synchronize_network_routes
from .routing.repository import (
    accept_proposal_routes,
    approve_routes,
    create_rule,
    create_route,
    delete_proposal as delete_routing_proposal,
    delete_rule,
    delete_route,
    get_proposal as get_routing_proposal,
    get_route,
    get_rule,
    list_audit_events,
    list_proposals as list_routing_proposals,
    list_route_versions,
    list_routes,
    list_rules,
    reject_routes,
    save_validation,
    update_proposal as update_routing_proposal,
    update_route,
    update_rule,
)
from .routing.validation import RoutingValidator, detect_routing_loop
from .capacity.service import CapacityTimingService, PreflightService
from .workflow.models import WORKFLOW_STEPS
from .workflow.service import WorkflowConflictError, WorkflowStatusService, is_topology_layout_only_change
from .intelligence import IntelligenceService
from .intelligence.reports import IntelligenceReportService
from .project_bundle import ProjectBundleService, normalize_project_id
from .project_context import activate_project
from .workloads import EngineeringWorkloadOrchestrator
from .simulation import (
    FAULTS_BY_SCOPE,
    list_fault_proposals,
    list_scenarios,
    propose_faults,
    review_fault_proposal,
    save_scenario,
    trace_metadata,
)
from .structure import apply_structure, evaluate_structure, reject_structure_proposal
from .structure_transfer import analyze_ecu_transfer, analyze_system_duplicates, apply_ecu_transfer, reject_ecu_transfer
from .system_merge import merge_system_duplicate
from .system_clusters import system_owners
from .tool_registry import get_engineering_tool, list_engineering_tools

engineering_api = Blueprint("engineering_api", __name__)
logger = logging.getLogger(__name__)

# URL-Segment (Plural, kebab-case) -> kanonischer Objekttyp
RESOURCES: dict[str, str] = {
    "hardware-nodes": "HardwareNode",
    "functions": "Function",
    "interfaces": "Interface",
    "messages": "Message",
    "signals": "Signal",
}

FILTERABLE_QUERY_PARAMS = (
    "domain",
    "lifecycle_state",
    "review_state",
    "approval_state",
    "hardware_node_id",
    "function_id",
    "interface_id",
    "message_id",
    "device_type",
    "interface_type",
)


def _topology_with_engineering_links(topology: dict, sync_result: dict) -> dict:
    synced_nodes = {
        str(node.get("topology_node_id")): node
        for node in sync_result.get("nodes", [])
        if isinstance(node, dict) and node.get("topology_node_id")
    }
    synced_edges = {
        str(edge.get("topology_edge_id")): edge
        for edge in sync_result.get("edges", [])
        if isinstance(edge, dict) and edge.get("topology_edge_id")
    }
    nodes = []
    interface_names_by_port: dict[str, str] = {}
    for raw_node in topology.get("nodes", []):
        if not isinstance(raw_node, dict):
            continue
        synced = synced_nodes.get(str(raw_node.get("id"))) or {}
        interfaces = {
            str(item.get("topology_port_id")): item
            for item in synced.get("interfaces", [])
            if isinstance(item, dict) and item.get("topology_port_id")
        }
        ports = []
        for port in raw_node.get("ports", []):
            if not isinstance(port, dict):
                continue
            synced_interface = interfaces.get(str(port.get("id"))) or {}
            interface_name = synced_interface.get("engineering_name") or port.get("name")
            if port.get("id") and interface_name:
                interface_names_by_port[str(port.get("id"))] = str(interface_name)
            ports.append(
                {
                    **port,
                    "name": interface_name,
                    "engineeringId": synced_interface.get("engineering_id")
                    or port.get("engineeringId"),
                }
            )
        nodes.append(
            {
                **raw_node,
                "engineeringId": synced.get("engineering_id") or raw_node.get("engineeringId"),
                "name": synced.get("engineering_name") or raw_node.get("name"),
                "engineeringFunctionId": synced.get("function_id")
                or raw_node.get("engineeringFunctionId"),
                "ports": ports,
            }
        )
    edges = []
    for edge in topology.get("edges", []):
        if not isinstance(edge, dict):
            continue
        edges.append(
            {
                **edge,
                "sourceInterfaceName": interface_names_by_port.get(str(edge.get("sourcePort")))
                or edge.get("sourceInterfaceName"),
                "targetInterfaceName": interface_names_by_port.get(str(edge.get("targetPort")))
                or edge.get("targetInterfaceName"),
                "engineeringRelationId": (
                    synced_edges.get(str(edge.get("id"))) or {}
                ).get("engineering_relation_id")
                or edge.get("engineeringRelationId"),
            }
        )
    topology = {"nodes": nodes, "edges": edges}
    kinds = {"ecu": "ECU", "gateway": "Gateway", "sensor": "SensorController", "actuator": "ActuatorController"}
    hardware = [{"id": node.get("engineeringId") or node["id"], "name": node.get("name"), "device_type": kinds.get(node.get("kind"))} for node in nodes]
    owners = system_owners(hardware, topology)
    for node in nodes:
        hardware_id = str(node.get("engineeringId") or node["id"])
        owner = owners.get(str(node.get("engineeringId") or node["id"]))
        if (
            owner
            and owner["basis"] != "unassigned"
            and (
                node.get("kind") in {"sensor", "actuator"}
                or (node.get("kind") == "ecu" and owner["id"] != hardware_id)
            )
        ):
            node["systemOwnerId"] = owner["id"]
            node["systemOwnerSource"] = owner["basis"]
    return topology


def _resource_object_type(resource: str) -> str:
    object_type = RESOURCES.get(resource)
    if object_type is None:
        raise EngineeringValidationError(f"Unbekannte Ressource: {resource!r}")
    return object_type


def _pagination_args() -> tuple[int, int]:
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        raise EngineeringValidationError("'limit' und 'offset' müssen ganze Zahlen sein.")
    return limit, offset


@engineering_api.errorhandler(EngineeringValidationError)
def _handle_validation_error(error: EngineeringValidationError):
    return jsonify({"error": str(error)}), 400


@engineering_api.errorhandler(NotFoundError)
def _handle_not_found(error: NotFoundError):
    return jsonify({"error": str(error)}), 404


@engineering_api.errorhandler(psycopg.errors.CheckViolation)
@engineering_api.errorhandler(psycopg.errors.ForeignKeyViolation)
@engineering_api.errorhandler(psycopg.errors.NotNullViolation)
def _handle_constraint_violation(error: psycopg.Error):
    return jsonify({"error": "Datenbank-Constraint verletzt.", "detail": str(error).strip()}), 400


@engineering_api.errorhandler(psycopg.errors.UniqueViolation)
def _handle_duplicate(error: psycopg.Error):
    logger.info("Duplicate engineering object or relation: %s", error)
    return jsonify({"error": "Das Engineering-Objekt oder die Relation existiert bereits."}), 409


@engineering_api.errorhandler(PoolTimeout)
@engineering_api.errorhandler(psycopg.OperationalError)
@engineering_api.errorhandler(psycopg.errors.UndefinedTable)
@engineering_api.errorhandler(psycopg.errors.UndefinedColumn)
@engineering_api.errorhandler(RuntimeError)
def _handle_database_unavailable(error: Exception):
    logger.exception("Engineering database unavailable")
    return (
        jsonify(
            {
                "error": "Engineering-Datenbank nicht erreichbar oder nicht konfiguriert.",
            }
        ),
        503,
    )


@engineering_api.errorhandler(WorkflowConflictError)
def _handle_workflow_conflict(error: WorkflowConflictError):
    return jsonify({"error": str(error)}), 409


def _project_id() -> str:
    payload = request.get_json(silent=True) if request.is_json else None
    return str(
        request.args.get("project_id")
        or (payload.get("project_id") if isinstance(payload, dict) else None)
        or request.headers.get("X-Project-ID")
        or "default"
    )


@engineering_api.before_request
def _activate_request_project() -> None:
    activate_project(_project_id())


def _auto_recalculate_capacity(project_id: str) -> None:
    """Refresh derived engineering metrics when enough source data exists."""
    state = WorkflowStatusService(project_id).get()
    required = {
        "engineering_model": "COMPLETE",
        "routing": "APPROVED",
        "network_editor": "COMPLETE",
        "parameters": "APPROVED",
    }
    if all(state["statuses"].get(step) == status for step, status in required.items()):
        result = CapacityTimingService(project_id).calculate()
        _diagnose_capacity_failure(project_id, result)


def _diagnose_capacity_failure(project_id: str, result: dict) -> None:
    if result.get("status") != "ERROR":
        return
    try:
        assessment = IntelligenceService(project_id).assess()
        result["diagnostic_snapshot_id"] = str(assessment.get("id") or "")
    except Exception as error:
        logger.exception("Capacity diagnosis failed for %s", project_id)
        result["diagnostic_error"] = str(error)


@engineering_api.after_request
def _propagate_source_changes(response):
    """Keep every existing mutation endpoint inside the workflow dependency graph."""
    if response.status_code >= 400 or request.method not in {"POST", "PATCH", "DELETE"}:
        return response
    relative_path = request.path.removeprefix("/api/engineering")
    if relative_path.startswith(("/workflow", "/capacity", "/preflight", "/intelligence", "/projects")):
        return response
    step = None
    reason = None
    status = "COMPLETE"
    if relative_path.startswith("/routing"):
        step = "routing"
        reason = "Die logische Routing-Tabelle wurde geaendert."
        active_routes = [
            route
            for route in list_routes(limit=500)
            if route.get("status") not in {"SUPERSEDED", "DEPRECATED", "REJECTED"}
        ]
        if not active_routes:
            status = "IN_PROGRESS"
            reason = "Routing-Vorschlaege wurden vorbereitet; die Routing-Tabelle ist noch leer."
        elif all(route.get("approval_state") == "APPROVED" for route in active_routes):
            status = "APPROVED"
            reason = "Alle aktiven Routen sind technisch geprueft und freigegeben."
        else:
            status = "WARNING"
            reason = "Die Routing-Tabelle enthaelt noch nicht freigegebene Routen."
    elif relative_path.startswith("/topology/sync"):
        return response
    elif (
        relative_path == "/proposals/approve-all-valid"
        or (relative_path.startswith("/proposals/") and relative_path.endswith("/approve"))
        or (
            relative_path.startswith("/workloads/")
            and relative_path.endswith(("/approve-selected", "/approve-all-valid"))
        )
    ) and getattr(g, "engineering_proposal_changed", False):
        step = "engineering_model"
        reason = "Ein freigegebener Engineering-Vorschlag wurde in das kanonische Modell uebernommen."
    elif relative_path.startswith(("/imports/commit", "/relations", "/structure/apply")) or (
        relative_path.startswith("/structure/transfer/")
        and relative_path.endswith("/apply")
        and getattr(g, "engineering_proposal_changed", False)
    ) or (
        relative_path == "/structure/system-duplicates/merge"
        and getattr(g, "engineering_proposal_changed", False)
    ) or any(
        relative_path.startswith(f"/{resource}") for resource in RESOURCES
    ):
        step = "engineering_model"
        reason = "Das kanonische Engineering-Modell wurde geaendert."
    if step:
        try:
            project_id = _project_id()
            WorkflowStatusService(project_id).mark_changed(
                step,
                reason or "Quelldaten geaendert.",
                status=status,
            )
            _auto_recalculate_capacity(project_id)
        except Exception:
            logger.exception("Workflow-Invalidierung konnte nicht persistiert werden")
    return response


@engineering_api.route("/health", methods=["GET"])
def health():
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM engineering_schema_migrations"
        ).fetchone()
    return jsonify(
        {
            "status": "ok",
            "service": "engineering-model",
            "schema_version": int(row["version"]),
        }
    )


@engineering_api.route("/schema", methods=["GET"])
def schema():
    """Metadaten für Frontend-Formulare: Vokabulare und Ressourcen-Layout."""
    return jsonify(
        {
            "resources": list(RESOURCES.keys()),
            "device_types": list(DEVICE_TYPES),
            "interface_types": list(INTERFACE_TYPES),
            "message_directions": list(MESSAGE_DIRECTIONS),
        }
    )


@engineering_api.route("/tools", methods=["GET"])
def tool_registry_route():
    approval = request.args.get("approval_required")
    approval_required = None
    if approval is not None:
        approval_required = approval.strip().lower() in {"1", "true", "yes", "ja"}
    tools = list_engineering_tools(
        category=request.args.get("category"),
        industry=request.args.get("industry"),
        status=request.args.get("status"),
        approval_required=approval_required,
        workflow_step=request.args.get("workflow_step"),
    )
    return jsonify({"items": tools, "count": len(tools)})


@engineering_api.route("/tools/<tool_id>", methods=["GET"])
def tool_registry_item_route(tool_id: str):
    return jsonify(get_engineering_tool(tool_id))


@engineering_api.route("/simulation/catalog", methods=["GET"])
def simulation_catalog_route():
    return jsonify(
        {
            "behavior_types": [
                "CONSTANT", "STEP", "RAMP", "LINEAR", "SINE", "TRIANGLE", "SAWTOOTH",
                "PULSE", "RANDOM_WALK", "BOUNDED_RANDOM", "STATE_DEPENDENT", "FORMULA",
                "LOOKUP_TABLE", "EXTERNAL_SERIES",
            ],
            "model_labels": [
                "PHYSICS_BASED", "RULE_BASED", "EMPIRICAL", "SYNTHETIC", "GENERIC_ESTIMATE",
            ],
            "faults": {scope.lower(): sorted(values) for scope, values in FAULTS_BY_SCOPE.items()},
            "fault_catalog": {
                scope.lower(): [
                    {
                        "id": fault_id,
                        "name": fault_id.replace("_", " ").title(),
                        "category": scope,
                        "applicable_object_types": [scope],
                        "parameters": ["target", "start_s", "end_s", "magnitude"],
                        "constraints": {"start_s": {"minimum": 0}, "end_s": {"after": "start_s"}},
                        "simulation_handler": "FaultInjectionEngine",
                    }
                    for fault_id in sorted(values)
                ]
                for scope, values in FAULTS_BY_SCOPE.items()
            },
            "modes": ["NORMAL", "USER_DEFINED_FAULT", "AI_GENERATED_FAULT", "STRESS"],
        }
    )


@engineering_api.route("/simulation/scenarios", methods=["GET"])
def simulation_scenarios_route():
    items = list_scenarios()
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/simulation/scenarios", methods=["POST"])
def create_simulation_scenario_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise EngineeringValidationError("Ein Szenario-Objekt wird erwartet.")
    return jsonify(save_scenario(payload)), 201


@engineering_api.route("/simulation/fault-proposals", methods=["GET"])
def simulation_fault_proposals_route():
    items = list_fault_proposals()
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/simulation/fault-proposals", methods=["POST"])
def create_simulation_fault_proposals_route():
    items = propose_faults()
    return jsonify({"items": items, "count": len(items)}), 201


@engineering_api.route("/simulation/fault-proposals/<proposal_id>/review", methods=["POST"])
def review_simulation_fault_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise EngineeringValidationError("Review-Daten werden erwartet.")
    return jsonify(review_fault_proposal(
        proposal_id,
        str(payload.get("action") or ""),
        str(payload.get("actor") or "user"),
        payload.get("changes") if isinstance(payload.get("changes"), dict) else None,
    ))


@engineering_api.route("/simulation/traces", methods=["GET"])
def simulation_trace_metadata_route():
    items = trace_metadata(request.args.get("job_id"))
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/topology/sync", methods=["POST"])
def sync_topology_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    project_id = _project_id()
    result = sync_topology(payload)
    if payload.get("persist_workflow", True) is not False:
        topology = _topology_with_engineering_links(payload, result)
        WorkflowStatusService(project_id).save_topology(
            topology,
            actor=str(payload.get("actor") or "network-editor"),
        )
        result["routing_sync"] = synchronize_network_routes(
            project_id,
            topology,
            actor=str(payload.get("actor") or "network-editor"),
        )
        _auto_recalculate_capacity(project_id)
    return jsonify(result)


@engineering_api.route("/imports/preview", methods=["POST"])
def preview_import_route():
    uploaded = request.files.get("file")
    if uploaded is None:
        return jsonify({"error": "Eine Datei im Feld 'file' wird erwartet."}), 400
    return jsonify(preview_import(uploaded.filename or "import", uploaded.read()))


@engineering_api.route("/imports/commit", methods=["POST"])
def commit_import_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(commit_import(payload)), 201


# ---------------------------------------------------------------------------
# Binding workflow, capacity/timing and preflight
# ---------------------------------------------------------------------------


@engineering_api.route("/workflow", methods=["GET"])
def workflow_status_route():
    return jsonify(
        WorkflowStatusService(_project_id()).get(
            summary=request.args.get("view", "").strip().lower() == "summary"
        )
    )


@engineering_api.route("/workflow/context", methods=["PATCH"])
def workflow_context_route():
    payload = _routing_payload()
    return jsonify(
        WorkflowStatusService(_project_id()).set_context(
            payload,
            summary=request.args.get("view", "").strip().lower() == "summary",
        )
    )


@engineering_api.route("/workflow/changed", methods=["POST"])
def workflow_changed_route():
    payload = _routing_payload()
    step = str(payload.get("step") or "")
    if step not in WORKFLOW_STEPS:
        raise EngineeringValidationError("step ist kein gueltiger Workflow-Schritt.")
    return jsonify(
        WorkflowStatusService(_project_id()).mark_changed(
            step,
            str(payload.get("reason") or "Quelldaten wurden geaendert."),
            status=str(payload.get("status") or "COMPLETE"),
            actor=payload.get("actor"),
        )
    )


@engineering_api.route("/workflow/parameters", methods=["GET"])
def workflow_parameters_route():
    state = WorkflowStatusService(_project_id()).get()
    return jsonify({"project_id": state["project_id"], "parameters": state["parameters"]})


@engineering_api.route("/workflow/parameters", methods=["PATCH"])
def update_workflow_parameters_route():
    payload = _routing_payload()
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else payload
    project_id = _project_id()
    WorkflowStatusService(project_id).save_parameters(parameters, actor=payload.get("actor"))
    _auto_recalculate_capacity(project_id)
    return jsonify(WorkflowStatusService(project_id).get())


@engineering_api.route("/workflow/topology", methods=["GET"])
def workflow_topology_route():
    state = WorkflowStatusService(_project_id()).get()
    return jsonify({"project_id": state["project_id"], "topology": state["topology"]})


@engineering_api.route("/workflow/topology", methods=["PUT"])
def update_workflow_topology_route():
    payload = _routing_payload()
    topology = payload.get("topology") if isinstance(payload.get("topology"), dict) else payload
    project_id = _project_id()
    actor = str(payload.get("actor") or "network-editor")
    workflow = WorkflowStatusService(project_id)
    if is_topology_layout_only_change(workflow.get()["topology"], topology):
        state = workflow.save_topology(topology, actor=actor)
        state["routing_sync"] = {
            "counts": {"created": 0, "outdated": 0, "unchanged": 0, "skipped": 0},
            "skipped": [],
        }
        return jsonify(state)
    sync_result = sync_topology(topology)
    topology = _topology_with_engineering_links(topology, sync_result)
    workflow.save_topology(topology, actor=actor)
    routing_sync = synchronize_network_routes(project_id, topology, actor=actor)
    _auto_recalculate_capacity(project_id)
    state = workflow.get()
    state["routing_sync"] = routing_sync
    return jsonify(state)


@engineering_api.route("/workflow/snapshots", methods=["GET"])
def workflow_snapshots_route():
    service = WorkflowStatusService(_project_id())
    capacity = service.latest_analysis("capacity_timing", include_outdated=True)
    preflight = service.latest_analysis("preflight", include_outdated=True)
    results_analysis = service.latest_analysis("results_analysis", include_outdated=True)
    state = service.get()
    return jsonify(
        {
            "capacity": capacity,
            "preflight": preflight,
            "results_analysis": results_analysis,
            "simulations": state["simulation_snapshots"],
        }
    )


@engineering_api.route("/workflow/simulation-snapshots", methods=["POST"])
def create_simulation_snapshot_route():
    payload = _routing_payload()
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise EngineeringValidationError("configuration muss ein Objekt sein.")
    return jsonify(
        WorkflowStatusService(_project_id()).create_simulation_snapshot(configuration)
    ), 201


@engineering_api.route("/workflow/simulation-snapshots/<snapshot_id>", methods=["GET"])
def get_simulation_snapshot_route(snapshot_id: str):
    snapshot = WorkflowStatusService(_project_id()).get_simulation_snapshot(snapshot_id)
    if snapshot is None:
        return jsonify({"error": "SimulationSnapshot nicht gefunden."}), 404
    return jsonify(snapshot)


# ---------------------------------------------------------------------------
# Data Science & Intelligence and portable projects
# ---------------------------------------------------------------------------


@engineering_api.route("/intelligence", methods=["GET"])
def intelligence_latest_route():
    snapshot = IntelligenceService(_project_id()).latest(include_outdated=True)
    if snapshot is None:
        return jsonify({"error": "Noch keine Intelligence-Bewertung vorhanden."}), 404
    return jsonify(snapshot)


@engineering_api.route("/intelligence/assess", methods=["POST"])
def intelligence_assess_route():
    return jsonify(IntelligenceService(_project_id()).assess())


@engineering_api.route("/intelligence/export", methods=["GET"])
def intelligence_export_route():
    snapshot = IntelligenceService(_project_id()).latest(include_outdated=True)
    if snapshot is None:
        return jsonify({"error": "Noch keine Intelligence-Bewertung vorhanden."}), 404
    report = IntelligenceReportService()
    export_format = str(request.args.get("format") or "json").lower()
    if export_format == "csv":
        content = report.csv_report(snapshot, str(request.args.get("section") or "issues"))
        return Response(content, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=intelligence-report.csv"})
    if export_format != "json":
        raise EngineeringValidationError("format muss json oder csv sein.")
    return Response(report.json_report(snapshot), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=intelligence-report.json"})


@engineering_api.route("/intelligence/proposals", methods=["GET"])
def intelligence_proposals_route():
    items = IntelligenceService(_project_id()).proposals(status=request.args.get("status"))
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/intelligence/proposals", methods=["POST"])
def intelligence_create_proposal_route():
    return jsonify(IntelligenceService(_project_id()).create_proposal(_routing_payload())), 201


@engineering_api.route("/intelligence/proposals/<proposal_id>", methods=["PATCH"])
def intelligence_review_proposal_route(proposal_id: str):
    return jsonify(IntelligenceService(_project_id()).review_proposal(proposal_id, _routing_payload()))


@engineering_api.route("/projects", methods=["GET"])
def list_projects_route():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT project_id, active_step, statuses, updated_at FROM engineering_workflow_projects ORDER BY updated_at DESC LIMIT 200"
        ).fetchall()
    return jsonify({"items": rows, "count": len(rows)})


@engineering_api.route("/projects/export", methods=["GET"])
def export_project_route():
    source = normalize_project_id(_project_id())
    target = request.args.get("target_project_id")
    service = ProjectBundleService()
    bundle = service.export(source, target_project_id=target)
    if target and normalize_project_id(target) != source:
        service.import_bundle(bundle, target_project_id=target)
    return jsonify(bundle)


@engineering_api.route("/projects/import", methods=["POST"])
def import_project_route():
    payload = _routing_payload()
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        raise EngineeringValidationError("bundle muss ein Objekt sein.")
    return jsonify(ProjectBundleService().import_bundle(bundle, target_project_id=payload.get("target_project_id")))


@engineering_api.route("/projects/reset", methods=["POST"])
def reset_project_route():
    payload = _routing_payload()
    project_id = payload.get("project_id") or payload.get("target_project_id") or _project_id()
    return jsonify(ProjectBundleService().reset_workspace(project_id))


def _capacity_result_section(section: str):
    snapshot = WorkflowStatusService(_project_id()).latest_analysis(
        "capacity_timing", include_outdated=True
    )
    if snapshot is None:
        return jsonify({"error": "Noch keine Capacity-Analyse vorhanden."}), 404
    return jsonify(
        {
            "snapshot_id": snapshot["id"],
            "status": snapshot["status"],
            "is_outdated": snapshot["is_outdated"],
            "outdated_reason": snapshot.get("outdated_reason"),
            "items": (snapshot.get("results") or {}).get(section, []),
        }
    )


@engineering_api.route("/capacity", methods=["GET"])
def capacity_latest_route():
    snapshot = CapacityTimingService(_project_id()).latest()
    if snapshot is None:
        return jsonify({"error": "Noch keine Capacity-Analyse vorhanden."}), 404
    return jsonify(snapshot)


@engineering_api.route("/capacity/calculate", methods=["POST"])
def calculate_capacity_route():
    payload = request.get_json(silent=True) or {}
    overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else None
    result = CapacityTimingService(_project_id()).calculate(overrides)
    _diagnose_capacity_failure(_project_id(), result)
    return jsonify(result)


@engineering_api.route("/capacity/scenario", methods=["POST"])
def capacity_scenario_route():
    payload = _routing_payload()
    overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else payload
    return jsonify(CapacityTimingService(_project_id()).calculate(overrides, persist=False))


@engineering_api.route("/capacity/optimize", methods=["POST"])
def capacity_optimize_route():
    service = CapacityTimingService(_project_id())
    result = service.calculate(persist=False)
    state = WorkflowStatusService(_project_id()).get()
    parameters = state.get("parameters") or {}
    proposals = []
    networks = result["results"].get("networks") or []
    routes = result["results"].get("routes") or []
    if networks:
        network = networks[0]
        current_bitrate = float(parameters.get("bitrate") or 1_000_000)
        scenario = service.calculate({"bitrate": current_bitrate * 2}, persist=False)
        proposals.append(
            {
                "id": f"OPT-BITRATE-{network['network_id']}",
                "status": "PROPOSAL",
                "kind": "INCREASE_BITRATE",
                "target_type": "Network",
                "target_id": network["network_id"],
                "summary": "Bitrate verdoppeln, um Peak-, Burst- und Queueing-Last zu reduzieren.",
                "changes": {"bitrate": {"from": current_bitrate, "to": current_bitrate * 2}},
                "expected_impact": scenario.get("impact"),
            }
        )
    if routes:
        route = routes[0]
        current_policy = str(parameters.get("queue_policy") or "FIFO")
        scenario = service.calculate({"queue_policy": "STRICT_PRIORITY"}, persist=False)
        proposals.append(
            {
                "id": f"OPT-QUEUE-{route['route_id']}",
                "status": "PROPOSAL",
                "kind": "QUEUE_POLICY",
                "target_type": "RoutingEntry",
                "target_id": route["route_id"],
                "summary": "Prioritaetsbasiertes Queueing als What-if gegen FIFO vergleichen.",
                "changes": {"queue_policy": {"from": current_policy, "to": "STRICT_PRIORITY"}},
                "expected_impact": scenario.get("impact"),
            }
        )
    return jsonify({"status": result["status"], "proposals": proposals, "applied": False})


@engineering_api.route("/capacity/networks", methods=["GET"])
def capacity_networks_route():
    return _capacity_result_section("networks")


@engineering_api.route("/capacity/networks/<network_id>", methods=["GET"])
def capacity_network_route(network_id: str):
    snapshot = WorkflowStatusService(_project_id()).latest_analysis(
        "capacity_timing", include_outdated=True
    )
    items = (snapshot.get("results") or {}).get("networks", []) if snapshot else []
    item = next((entry for entry in items if entry.get("network_id") == network_id), None)
    if item is None:
        return jsonify({"error": "Netzwerk nicht in der Capacity-Analyse gefunden."}), 404
    return jsonify(item)


@engineering_api.route("/capacity/calculate/network/<network_id>", methods=["POST"])
def calculate_capacity_network_route(network_id: str):
    payload = request.get_json(silent=True) or {}
    overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
    result = CapacityTimingService(_project_id()).calculate(overrides, persist=False)
    network = next(
        (item for item in result["results"].get("networks", []) if item.get("network_id") == network_id),
        None,
    )
    if network is None:
        return jsonify({"error": "Netzwerk nicht in der Capacity-Analyse gefunden."}), 404
    return jsonify(
        {
            "project_id": result["project_id"],
            "status": result["status"],
            "network": network,
            "routes": [item for item in result["results"].get("routes", []) if item.get("network_id") == network_id],
            "messages": [item for item in result["results"].get("messages", []) if item.get("network_id") == network_id],
            "provenance": result["provenance"],
            "scenario": True,
        }
    )


@engineering_api.route("/capacity/messages", methods=["GET"])
def capacity_messages_route():
    return _capacity_result_section("messages")


@engineering_api.route("/capacity/routes", methods=["GET"])
def capacity_routes_route():
    return _capacity_result_section("routes")


@engineering_api.route("/capacity/gateways", methods=["GET"])
def capacity_gateways_route():
    return _capacity_result_section("gateways")


@engineering_api.route("/preflight", methods=["GET"])
def preflight_latest_route():
    snapshot = WorkflowStatusService(_project_id()).latest_analysis(
        "preflight", include_outdated=True
    )
    if snapshot is None:
        return jsonify({"error": "Noch kein Preflight vorhanden."}), 404
    return jsonify(snapshot)


@engineering_api.route("/preflight", methods=["POST"])
def run_preflight_route():
    return jsonify(PreflightService(_project_id()).run())


@engineering_api.route("/knowledge/search", methods=["POST"])
def knowledge_search_route():
    payload = _routing_payload()
    query = str(payload.get("query") or "").strip()
    if not query:
        raise EngineeringValidationError("query darf nicht leer sein.")
    selected = payload.get("selected_object_ids") or []
    if not isinstance(selected, list):
        raise EngineeringValidationError("selected_object_ids muss eine Liste sein.")
    filters = payload.get("filters") or {}
    if not isinstance(filters, dict):
        raise EngineeringValidationError("filters muss ein Objekt sein.")
    limit = min(max(int(payload.get("limit") or 20), 1), 50)
    return jsonify(
        CanonicalKnowledgeService().search(
            query,
            selected_object_ids=[str(value) for value in selected],
            filters={key: value for key, value in filters.items() if value is not None},
            limit=limit,
        )
    )


@engineering_api.route("/knowledge/subgraph", methods=["POST"])
def knowledge_subgraph_route():
    payload = _routing_payload()
    object_ids = payload.get("object_ids") or []
    if not isinstance(object_ids, list) or not object_ids:
        raise EngineeringValidationError("object_ids muss eine nicht-leere Liste sein.")
    depth = min(max(int(payload.get("depth") or 2), 0), 5)
    return jsonify(CanonicalKnowledgeService().subgraph([str(value) for value in object_ids], depth=depth))


# ---------------------------------------------------------------------------
# Routing Manager
# ---------------------------------------------------------------------------


def _routing_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise EngineeringValidationError("Ein JSON-Objekt wird erwartet.")
    return payload


def _route_ids(payload: dict) -> list[str]:
    route_ids = payload.get("route_ids")
    if not isinstance(route_ids, list) or not route_ids:
        raise EngineeringValidationError("route_ids muss eine nicht-leere Liste sein.")
    return [str(route_id) for route_id in route_ids]


@engineering_api.route("/routing", methods=["GET"])
def list_routing_entries_route():
    limit, offset = _pagination_args()
    items = list_routes(
        status=request.args.get("status"),
        approval_state=request.args.get("approval_state"),
        origin=request.args.get("origin"),
        limit=limit,
        offset=offset,
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing", methods=["POST"])
def create_routing_entry_route():
    return jsonify(create_route(_routing_payload())), 201


@engineering_api.route("/routing/schema", methods=["GET"])
def routing_schema_route():
    from .routing.models import PRIORITIES, PROTOCOLS, REDUNDANCY_MODES, ROUTING_TYPES

    return jsonify(
        {
            "routing_types": list(ROUTING_TYPES),
            "protocols": list(PROTOCOLS),
            "priorities": list(PRIORITIES),
            "redundancy_modes": list(REDUNDANCY_MODES),
            "permissions": [
                "ROUTING_READ",
                "ROUTING_CREATE",
                "ROUTING_EDIT",
                "ROUTING_GENERATE",
                "ROUTING_VALIDATE",
                "ROUTING_REVIEW",
                "ROUTING_APPROVE",
                "ROUTING_ADMIN",
            ],
            "agent_permissions": ["ROUTING_READ", "ROUTING_GENERATE", "ROUTING_VALIDATE"],
        }
    )


@engineering_api.route("/routing/validate", methods=["POST"])
def validate_routing_table_route():
    routes = list_routes(limit=500)
    return jsonify(RoutingValidator(project_id=_project_id()).validate_table(routes))


@engineering_api.route("/routing/generate", methods=["POST"])
def generate_routing_route():
    return jsonify(RoutingGenerationService().generate_routes(_routing_payload())), 201


@engineering_api.route("/routing/paths", methods=["GET"])
def find_routing_paths_route():
    source = request.args.get("source")
    target = request.args.get("target")
    if not source or not target:
        raise EngineeringValidationError("source und target sind erforderlich.")
    return jsonify({"items": RoutingGenerationService().find_candidate_paths(source, target)})


@engineering_api.route("/routing/optimize", methods=["POST"])
def optimize_routing_route():
    payload = _routing_payload()
    routes = payload.get("routes") if isinstance(payload.get("routes"), list) else list_routes(limit=500)
    return jsonify({"items": RoutingGenerationService().optimize_routes(routes)})


@engineering_api.route("/routing/import", methods=["POST"])
def import_routing_route():
    payload = _routing_payload()
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        raise EngineeringValidationError("routes muss eine nicht-leere Liste sein.")
    created = [create_route({**route, "origin": "IMPORTED", "actor": payload.get("actor")}) for route in routes]
    return jsonify({"items": created, "count": len(created)}), 201


@engineering_api.route("/routing/approved/config", methods=["GET"])
def approved_routing_config_route():
    routes = list_routes(approval_state="APPROVED", limit=500)
    return jsonify(CommunicationConfigBuilder().build(routes))


@engineering_api.route("/routing/proposals", methods=["GET"])
def list_routing_proposals_route():
    limit, offset = _pagination_args()
    items = list_routing_proposals(
        status=request.args.get("status"), limit=limit, offset=offset
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/proposals/<proposal_id>", methods=["GET"])
def get_routing_proposal_route(proposal_id: str):
    return jsonify(get_routing_proposal(proposal_id))


@engineering_api.route("/routing/proposals/<proposal_id>", methods=["PATCH"])
def update_routing_proposal_route(proposal_id: str):
    return jsonify(update_routing_proposal(proposal_id, _routing_payload()))


@engineering_api.route("/routing/proposals/<proposal_id>", methods=["DELETE"])
def delete_routing_proposal_route(proposal_id: str):
    delete_routing_proposal(proposal_id, actor=request.args.get("actor"))
    return "", 204


@engineering_api.route("/routing/proposals/<proposal_id>/accept", methods=["POST"])
def accept_routing_proposal_route(proposal_id: str):
    payload = _routing_payload()
    indexes = payload.get("indexes", [])
    if not isinstance(indexes, list):
        raise EngineeringValidationError("indexes muss eine Liste sein.")
    items = accept_proposal_routes(
        proposal_id, [int(index) for index in indexes], actor=payload.get("actor")
    )
    return jsonify({"items": items, "count": len(items)}), 201


@engineering_api.route("/routing/approve-selected", methods=["POST"])
def approve_selected_routes_route():
    payload = _routing_payload()
    items = approve_routes(_route_ids(payload), actor=payload.get("actor"))
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/approve-all-valid", methods=["POST"])
def approve_all_valid_routes_route():
    payload = _routing_payload()
    items = approve_routes([], actor=payload.get("actor"), approve_all_valid=True)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/reject-selected", methods=["POST"])
def reject_selected_routes_route():
    payload = _routing_payload()
    items = reject_routes(
        _route_ids(payload), actor=payload.get("actor"), reason=payload.get("reason")
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/audit", methods=["GET"])
def routing_audit_route():
    items = list_audit_events(request.args.get("route_id"))
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/rules", methods=["GET"])
def list_routing_rules_route():
    items = list_rules(status=request.args.get("status"))
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/routing/rules", methods=["POST"])
def create_routing_rule_route():
    return jsonify(create_rule(_routing_payload())), 201


@engineering_api.route("/routing/rules/<rule_id>", methods=["GET"])
def get_routing_rule_route(rule_id: str):
    return jsonify(get_rule(rule_id))


@engineering_api.route("/routing/rules/<rule_id>", methods=["PATCH"])
def update_routing_rule_route(rule_id: str):
    return jsonify(update_rule(rule_id, _routing_payload()))


@engineering_api.route("/routing/rules/<rule_id>", methods=["DELETE"])
def delete_routing_rule_route(rule_id: str):
    delete_rule(rule_id, actor=request.args.get("actor"))
    return "", 204


@engineering_api.route("/routing/<route_id>", methods=["GET"])
def get_routing_entry_route(route_id: str):
    return jsonify(get_route(route_id))


@engineering_api.route("/routing/<route_id>", methods=["PATCH"])
def update_routing_entry_route(route_id: str):
    return jsonify(update_route(route_id, _routing_payload()))


@engineering_api.route("/routing/<route_id>", methods=["DELETE"])
def delete_routing_entry_route(route_id: str):
    delete_route(route_id, actor=request.args.get("actor"))
    return "", 204


@engineering_api.route("/routing/<route_id>/validate", methods=["POST"])
def validate_routing_entry_route(route_id: str):
    payload = _routing_payload()
    route = get_route(route_id)
    result = RoutingValidator(project_id=_project_id()).validate(route, exclude_route_id=route_id)
    return jsonify(save_validation(route_id, result, actor=payload.get("actor")))


@engineering_api.route("/routing/<route_id>/approve", methods=["POST"])
def approve_routing_entry_route(route_id: str):
    payload = _routing_payload()
    return jsonify(approve_routes([route_id], actor=payload.get("actor"))[0])


@engineering_api.route("/routing/<route_id>/reject", methods=["POST"])
def reject_routing_entry_route(route_id: str):
    payload = _routing_payload()
    return jsonify(
        reject_routes([route_id], actor=payload.get("actor"), reason=payload.get("reason"))[0]
    )


@engineering_api.route("/routing/<route_id>/path", methods=["GET"])
def routing_entry_path_route(route_id: str):
    route = get_route(route_id)
    return jsonify(
        {
            "route_id": route_id,
            "hops": route["route"].get("hops", []),
            "gateways": route["route"].get("gateways", []),
            "transformations": route["route"].get("transformations", []),
            "loop_nodes": detect_routing_loop(route["route"].get("hops", [])),
        }
    )


@engineering_api.route("/routing/<route_id>/evidence", methods=["GET"])
def routing_entry_evidence_route(route_id: str):
    route = get_route(route_id)
    return jsonify(
        {
            "route_id": route_id,
            "route_code": route["route_code"],
            "origin": route["origin"],
            "confidence": route["confidence"],
            "evidence": route.get("validation", {}).get("evidence", []),
            "technical_reason": {
                "source": route["source"],
                "destinations": route["destinations"],
                "protocol": route["source"].get("protocol"),
                "timing": route.get("validation", {}).get("metrics", {}),
                "path": route["route"].get("hops", []),
            },
        }
    )


@engineering_api.route("/routing/<route_id>/versions", methods=["GET"])
def routing_entry_versions_route(route_id: str):
    route = get_route(route_id)
    return jsonify({"items": list_route_versions(route["route_code"])})


# ---------------------------------------------------------------------------
# Engineering Workloads
# ---------------------------------------------------------------------------


def _workload_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise EngineeringValidationError("Ein JSON-Objekt wird erwartet.")
    return payload


@engineering_api.route("/workloads/registry", methods=["GET"])
def workload_registry_route():
    orchestrator = EngineeringWorkloadOrchestrator(_project_id())
    return jsonify({"types": orchestrator.registry.types()})


@engineering_api.route("/workloads", methods=["GET"])
def list_workloads_route():
    limit, offset = _pagination_args()
    items = EngineeringWorkloadOrchestrator(_project_id()).list_workloads(
        status=request.args.get("status"),
        workload_type=request.args.get("workload_type"),
        limit=limit,
        offset=offset,
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/workloads", methods=["POST"])
def create_workload_route():
    workload = EngineeringWorkloadOrchestrator(_project_id()).create_workload(_workload_payload())
    return jsonify(workload), 201


@engineering_api.route("/workloads/<workload_id>", methods=["GET"])
def get_workload_route(workload_id: str):
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).get_workload(workload_id))


@engineering_api.route("/workloads/<workload_id>/start", methods=["POST"])
def start_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(
        EngineeringWorkloadOrchestrator(_project_id()).start_workload(
            workload_id,
            actor=payload.get("actor"),
        )
    )


@engineering_api.route("/workloads/<workload_id>/pause", methods=["POST"])
def pause_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).pause(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/resume", methods=["POST"])
def resume_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).resume(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/cancel", methods=["POST"])
def cancel_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).cancel(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/validate", methods=["POST"])
def validate_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).validate_workload(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/generate-missing", methods=["POST"])
def generate_missing_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).generate_missing(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/retry-invalid", methods=["POST"])
def retry_invalid_workload_route(workload_id: str):
    payload = _workload_payload()
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).retry_invalid(workload_id, actor=payload.get("actor")))


@engineering_api.route("/workloads/<workload_id>/progress", methods=["GET"])
def workload_progress_route(workload_id: str):
    return jsonify(EngineeringWorkloadOrchestrator(_project_id()).progress(workload_id))


@engineering_api.route("/workloads/<workload_id>/objects", methods=["GET"])
def workload_objects_route(workload_id: str):
    items = EngineeringWorkloadOrchestrator(_project_id()).list_workload_objects(workload_id)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/workloads/<workload_id>/dependencies", methods=["GET"])
def workload_dependencies_route(workload_id: str):
    items = EngineeringWorkloadOrchestrator(_project_id()).dependencies(workload_id)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/workloads/<workload_id>/events", methods=["GET"])
def workload_events_route(workload_id: str):
    items = EngineeringWorkloadOrchestrator(_project_id()).list_events(workload_id)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/workloads/<workload_id>/audit", methods=["GET"])
def workload_audit_route(workload_id: str):
    items = EngineeringWorkloadOrchestrator(_project_id()).list_events(workload_id)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/workloads/<workload_id>/approve-selected", methods=["POST"])
def approve_selected_workload_route(workload_id: str):
    payload = _workload_payload()
    selections = payload.get("selections")
    if not isinstance(selections, dict):
        raise EngineeringValidationError("selections muss Proposal-IDs auf Indexlisten abbilden.")
    before = EngineeringWorkloadOrchestrator(_project_id()).list_workload_objects(workload_id)
    canonical_before = sum(bool(item.get("canonical_id")) for item in before)
    result = EngineeringWorkloadOrchestrator(_project_id()).approve_valid(
        workload_id,
        actor=str(payload.get("actor") or ""),
        selections=selections,
    )
    after = EngineeringWorkloadOrchestrator(_project_id()).list_workload_objects(workload_id)
    g.engineering_proposal_changed = sum(bool(item.get("canonical_id")) for item in after) > canonical_before
    return jsonify(result)


@engineering_api.route("/workloads/<workload_id>/approve-all-valid", methods=["POST"])
def approve_all_valid_workload_route(workload_id: str):
    payload = _workload_payload()
    orchestrator = EngineeringWorkloadOrchestrator(_project_id())
    before = orchestrator.list_workload_objects(workload_id)
    canonical_before = sum(bool(item.get("canonical_id")) for item in before)
    result = orchestrator.approve_valid(workload_id, actor=str(payload.get("actor") or ""))
    after = orchestrator.list_workload_objects(workload_id)
    g.engineering_proposal_changed = sum(bool(item.get("canonical_id")) for item in after) > canonical_before
    return jsonify(result)


@engineering_api.route("/structure/evaluate", methods=["POST"])
def evaluate_structure_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(evaluate_structure(payload)), 201


@engineering_api.route("/structure/apply", methods=["POST"])
def apply_structure_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    result = apply_structure(payload)
    g.engineering_proposal_changed = bool(result.get("count"))
    return jsonify(result)


@engineering_api.route("/structure/proposals/<proposal_id>/reject", methods=["POST"])
def reject_structure_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    return jsonify(
        reject_structure_proposal(
            proposal_id,
            actor=str(payload.get("actor") or "structure-tree-reviewer"),
        )
    )


@engineering_api.route("/structure/transfer/analyze", methods=["POST"])
def analyze_ecu_transfer_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(analyze_ecu_transfer(payload)), 201


@engineering_api.route("/structure/system-duplicates", methods=["GET"])
def analyze_system_duplicates_route():
    return jsonify(analyze_system_duplicates())


@engineering_api.route("/structure/system-duplicates/merge", methods=["POST"])
def merge_system_duplicate_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    result = merge_system_duplicate(payload)
    g.engineering_proposal_changed = True
    return jsonify(result)


@engineering_api.route("/structure/transfer/<proposal_id>/apply", methods=["POST"])
def apply_ecu_transfer_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    result = apply_ecu_transfer(
        proposal_id,
        actor=str(payload.get("actor") or "structure-transfer-reviewer"),
        decisions=payload.get("decisions") if isinstance(payload.get("decisions"), list) else None,
    )
    g.engineering_proposal_changed = bool(result.get("created"))
    return jsonify(result)


@engineering_api.route("/structure/transfer/<proposal_id>/reject", methods=["POST"])
def reject_ecu_transfer_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    return jsonify(
        reject_ecu_transfer(
            proposal_id,
            actor=str(payload.get("actor") or "structure-transfer-reviewer"),
        )
    )


@engineering_api.route("/<resource>", methods=["GET"])
def list_resource(resource: str):
    object_type = _resource_object_type(resource)
    limit, offset = _pagination_args()
    filters = {key: request.args.get(key) for key in FILTERABLE_QUERY_PARAMS if request.args.get(key)}
    items = list_objects(object_type, filters=filters, limit=limit, offset=offset)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/<resource>", methods=["POST"])
def create_resource(resource: str):
    object_type = _resource_object_type(resource)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    if payload.get("source") == "ai_generated":
        return jsonify({"error": "KI-Ergebnisse müssen zuerst als AIProposal gespeichert werden."}), 409
    if payload.get("approval_state") not in (None, "pending"):
        return jsonify({"error": "Freigaben sind nur über den Approval-Service zulässig."}), 409
    item = create_object(object_type, payload)
    return jsonify(item), 201


@engineering_api.route("/<resource>/<object_id>", methods=["GET"])
def get_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    return jsonify(get_object(object_type, object_id))


@engineering_api.route("/<resource>/<object_id>", methods=["PATCH"])
def update_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    if "approval_state" in payload:
        return jsonify({"error": "Freigaben sind nur über den Approval-Service zulässig."}), 409
    item = update_object(object_type, object_id, payload)
    return jsonify(item)


@engineering_api.route("/<resource>/<object_id>", methods=["DELETE"])
def delete_resource(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    delete_object(object_type, object_id)
    return "", 204


@engineering_api.route("/<resource>/<object_id>/versions", methods=["GET"])
def resource_versions(resource: str, object_id: str):
    object_type = _resource_object_type(resource)
    return jsonify({"items": list_versions(object_type, object_id)})


# ---------------------------------------------------------------------------
# Relations (Kanten des zukünftigen Knowledge Graphs)
# ---------------------------------------------------------------------------


@engineering_api.route("/relations", methods=["GET"])
def list_relations_route():
    limit, offset = _pagination_args()
    items = list_relations(
        object_type=request.args.get("object_type"),
        object_id=request.args.get("object_id"),
        relation_type=request.args.get("relation_type"),
        limit=limit,
        offset=offset,
    )
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/relations", methods=["POST"])
def create_relation_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    if payload.get("source") == "ai_generated":
        return jsonify({"error": "KI-Relations müssen zuerst als AIProposal gespeichert werden."}), 409
    item = create_relation(payload)
    return jsonify(item), 201


@engineering_api.route("/relations/<relation_id>", methods=["GET"])
def get_relation_route(relation_id: str):
    return jsonify(get_relation(relation_id))


@engineering_api.route("/relations/<relation_id>", methods=["DELETE"])
def delete_relation_route(relation_id: str):
    delete_relation(relation_id)
    return "", 204


@engineering_api.route("/proposals", methods=["GET"])
def list_proposals_route():
    limit, offset = _pagination_args()
    items = list_proposals(status=request.args.get("status"), limit=limit, offset=offset)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/proposals", methods=["POST"])
def create_proposal_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(create_proposal(payload)), 201


@engineering_api.route("/proposals/<proposal_id>", methods=["GET"])
def get_proposal_route(proposal_id: str):
    return jsonify(get_proposal(proposal_id))


@engineering_api.route("/proposals/<proposal_id>", methods=["PATCH"])
def update_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(update_proposal(proposal_id, payload))


@engineering_api.route("/proposals/<proposal_id>/validate", methods=["POST"])
def validate_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    return jsonify(validate_proposal(proposal_id, actor=payload.get("actor")))


@engineering_api.route("/proposals/<proposal_id>/approve", methods=["POST"])
def approve_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    indexes = payload.get("indexes")
    if indexes is not None and not isinstance(indexes, list):
        raise EngineeringValidationError("indexes muss eine Liste sein.")
    before = get_proposal(proposal_id)
    canonical_before = sum(bool(item.get("canonical_id")) for item in before.get("proposed_objects") or [])
    approved = approve_proposal(proposal_id, indexes=indexes, actor=payload.get("actor"))
    approved_items = approved.get("proposed_objects") or []
    canonical_after = sum(bool(item.get("canonical_id")) for item in approved_items)
    newly_registered = [
        item
        for index, item in enumerate(approved_items)
        if item.get("canonical_id")
        and not (
            index < len(before.get("proposed_objects") or [])
            and (before.get("proposed_objects") or [])[index].get("canonical_id")
        )
    ]
    g.engineering_proposal_changed = canonical_after > canonical_before and any(
        (item.get("canonical_resolution") or {}).get("strategy") != "semantic_hardware_reuse"
        for item in newly_registered
    )
    return jsonify(approved)


@engineering_api.route("/proposals/<proposal_id>/reject", methods=["POST"])
def reject_proposal_route(proposal_id: str):
    payload = request.get_json(silent=True) or {}
    return jsonify(reject_proposal(proposal_id, actor=payload.get("actor")))


@engineering_api.route("/proposals/approve-all-valid", methods=["POST"])
def approve_all_valid_proposals_route():
    payload = request.get_json(silent=True) or {}
    items = approve_all_valid_proposals(actor=payload.get("actor"))
    g.engineering_proposal_changed = bool(items)
    return jsonify({"items": items, "count": len(items)})


# Sicherstellen, dass alle registrierten Ressourcen tatsächlich Specs haben
# (fällt zur Importzeit auf, falls ein neuer Eintrag in RESOURCES vergessen
# wurde, in ENTITY_SPECS nachzuziehen).
assert set(RESOURCES.values()) <= set(ENTITY_SPECS), "RESOURCES referenziert unbekannten Objekttyp"
