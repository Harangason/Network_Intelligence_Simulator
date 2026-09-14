"""REST-Schnittstellen für das kanonische Engineering-Modell.

Dieses Blueprint stellt ausschließlich CRUD- und Versionierungs-Endpunkte für
Engineering-Objekte (HardwareNode, Function, Interface, Message, Signal),
deren Relations sowie kontrollierte Knowledge-Abfragen bereit. Simulation und
Agent bleiben getrennt; Retrieval liest ausschließlich die Source of Truth.
"""

from __future__ import annotations

import logging
import json

import psycopg
from flask import Blueprint, Response, g, jsonify, request, make_response
from psycopg_pool import PoolTimeout

from backend.agent_core.errors import RegistryLookupError
from .models import (
    CLASSIFICATION_STATUSES,
    DATA_COMPLEXITIES,
    DEVICE_TYPES,
    DEVICE_TYPINGS,
    EngineeringValidationError,
    INTERFACE_TYPES,
    MESSAGE_DIRECTIONS,
)
from .device_classification import DeviceClassificationRegistry
from .db import get_connection, RequestUnit, ConcurrentUpdateError, check_revision
from .performance_governance import assert_within_budget, performance_governance_summary
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
from .semantic_intelligence import SemanticClassificationService
from backend.intelligence.ml import MLInferenceService
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
from .workflow.service import WorkflowConflictError, WorkflowStatusService, is_topology_layout_only_change, check_edit_token
from .intelligence import IntelligenceService
from .intelligence.network_planning import communication_system_inventory, plan_network_distribution
from .intelligence.resource_policy import planning_policy
from .intelligence.reports import IntelligenceReportService
from .project_bundle import ProjectBundleService, normalize_project_id
from .project_context import activate_project, current_project_id, normalize_context_project_id, reset_project
from .pagination import all_pages
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
from .addressing import (
    AddressResolutionService,
    LogicalNodeAddressAllocator,
    create_technology_address_binding,
)
from .assignment_learning import EquipmentAssignmentLearningService

engineering_api = Blueprint("engineering_api", __name__)
logger = logging.getLogger(__name__)


@engineering_api.route('/communication-resources', methods=['GET'])
def inspect_communication_resources_route():
    from .goal_execution.graph import ModelGraphService
    graph = ModelGraphService.load()
    return jsonify({'model_revision': graph.revision, 'resources': graph.resources,
        'ports': [p for owner in graph.hardware for p in graph.find_ports(owner)]})


@engineering_api.route('/communication-resources/<kind>', methods=['PUT'])
def record_communication_hardware_fact_route(kind):
    from .goal_execution.resources import record_hardware_fact
    payload = request.get_json(silent=True) or {}
    return jsonify(record_hardware_fact(kind, payload.get('resource') or {}, payload.get('expected_revision')))


@engineering_api.route('/execution-goals/<workload_id>', methods=['GET'])
def inspect_execution_goal_route(workload_id):
    from .goal_execution.store import get_goal
    return jsonify(get_goal(workload_id))

# URL-Segment (Plural, kebab-case) -> kanonischer Objekttyp
RESOURCES: dict[str, str] = {
    "hardware-nodes": "HardwareNode",
    "hardware-interfaces": "HardwareNetworkInterface",
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
    "hardware_interface_id",
    "function_id",
    "interface_id",
    "message_id",
    "device_type",
    "device_class",
    "device_typing",
    "data_complexity",
    "classification_status",
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
            hardware_interface_id = synced_interface.get("hardware_interface_id") \
                or port.get("hardwareInterfaceId")
            if port.get("id") and interface_name:
                interface_names_by_port[str(port.get("id"))] = str(interface_name)
            ports.append(
                {
                    **port,
                    "name": interface_name,
                    "engineeringId": port.get("engineeringId") if hardware_interface_id else (
                        synced_interface.get("engineering_id") or port.get("engineeringId")
                    ),
                    "hardwareInterfaceId": hardware_interface_id,
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
    canonical_hardware = {str(item["id"]): item for item in all_pages(list_objects, "HardwareNode")}
    hardware = [{**canonical_hardware.get(str(node.get("engineeringId") or node["id"]), {}),
                 "id": node.get("engineeringId") or node["id"], "name": node.get("name"),
                 "device_type": canonical_hardware.get(str(node.get("engineeringId") or node["id"]), {}).get("device_type") or kinds.get(node.get("kind"))} for node in nodes]
    owners = system_owners(hardware, topology)
    for node in nodes:
        hardware_id = str(node.get("engineeringId") or node["id"])
        identity = canonical_hardware.get(hardware_id, {}).get('identity') or {}
        if identity.get('cluster_id'):
            node.update(clusterId=identity['cluster_id'], clusterName=identity.get('cluster_name'))
        if identity.get('system_owner_source') == 'network-editor':
            node.update(systemOwnerId=identity.get('system_owner_id'), systemOwnerSource='network-editor')
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


def _budgeted_json(name: str, payload: dict):
    try:
        assert_within_budget(name, len(json.dumps(payload, default=str).encode("utf-8")))
    except ValueError as error:
        return jsonify({"error": str(error), "budget": name}), 413
    return jsonify(payload)


@engineering_api.errorhandler(EngineeringValidationError)
def _handle_validation_error(error: EngineeringValidationError):
    return jsonify({"error": str(error)}), 400


@engineering_api.errorhandler(NotFoundError)
def _handle_not_found(error: NotFoundError):
    return jsonify({"error": str(error)}), 404


@engineering_api.errorhandler(RegistryLookupError)
def _handle_registry_lookup_error(error: RegistryLookupError):
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
@engineering_api.errorhandler(ConcurrentUpdateError)
@engineering_api.errorhandler(psycopg.errors.LockNotAvailable)
def _handle_workflow_conflict(error: WorkflowConflictError):
    return jsonify({"error": str(error)}), 409


def _project_id() -> str:
    payload = request.get_json(silent=True) if request.is_json else None
    return normalize_context_project_id(
        request.args.get("project")
        or request.args.get("project_id")
        or request.args.get("projectId")
        or (payload.get("project") if isinstance(payload, dict) else None)
        or (payload.get("project_id") if isinstance(payload, dict) else None)
        or (payload.get("projectId") if isinstance(payload, dict) else None)
        or request.headers.get("X-Project-ID")
        or "default"
    )


@engineering_api.before_request
def _activate_request_project() -> None:
    g.engineering_project_token = activate_project(_project_id())
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        g.engineering_unit = RequestUnit(_project_id())


# Registered before propagation: Flask runs after_request hooks in reverse order.
@engineering_api.after_request
def _finish_engineering_transaction(response):
    unit = getattr(g, "engineering_unit", None)
    if unit is not None:
        try:
            unit.finish(response.status_code < 400)
        except Exception:
            logger.exception("Engineering transaction could not be committed")
            return make_response(jsonify({"error": "Änderung konnte nicht vollständig gespeichert werden. Bitte neu laden."}), 503)
    response.headers["Cache-Control"] = "no-store"
    return response


@engineering_api.teardown_request
def _close_engineering_transaction(error=None):
    unit = g.pop("engineering_unit", None)
    if unit is not None:
        unit.close()
    token = g.pop("engineering_project_token", None)
    if token is not None:
        reset_project(token)


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
        if getattr(g, "routing_validation_failed", False):
            status = "ERROR"
            reason = "Die Routing-Tabelle enthaelt fachlich ungueltige Gateway-Fanout-Endpunkte."
        elif not active_routes:
            status = "IN_PROGRESS"
            reason = "Routing-Vorschlaege wurden vorbereitet; die Routing-Tabelle ist noch leer."
        elif any(
            route.get("status") == "CONFLICT"
            or (isinstance(route.get("validation"), dict) and route["validation"].get("valid") is False)
            for route in active_routes
        ):
            status = "ERROR"
            reason = "Die Routing-Tabelle enthaelt ungueltige Routen und muss ueberarbeitet werden."
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
        except Exception:
            logger.exception("Workflow-Invalidierung konnte nicht persistiert werden")
            return make_response(jsonify({"error": "Workflow konnte nicht aktualisiert werden. Die Änderung wurde zurückgerollt."}), 503)
        try:
            _auto_recalculate_capacity(project_id)
        except Exception:
            logger.exception("Automatische Neuberechnung fehlgeschlagen; Ergebnisse bleiben veraltet")
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


@engineering_api.route("/performance/governance", methods=["GET"])
def performance_governance():
    return jsonify(performance_governance_summary())


@engineering_api.route("/schema", methods=["GET"])
def schema():
    """Metadaten für Frontend-Formulare: Vokabulare und Ressourcen-Layout."""
    registry = DeviceClassificationRegistry()
    return jsonify(
        {
            "resources": list(RESOURCES.keys()),
            "device_types": list(DEVICE_TYPES),
            "device_classes": registry.class_options(),
            "device_typings": list(DEVICE_TYPINGS),
            "data_complexities": list(DATA_COMPLEXITIES),
            "classification_statuses": list(CLASSIFICATION_STATUSES),
            "device_capability_profiles": registry.profile_options(),
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
    items = propose_faults(model_review=True)
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


def _sync_topology_with_invalidation(topology: dict, project_id: str):
    result = sync_topology(topology)
    unit = getattr(g, "engineering_unit", None)
    if unit is not None and unit.model_changed:
        WorkflowStatusService(project_id).mark_changed(
            "engineering_model", "Netzwerkabgleich hat kanonische Objekte geändert."
        )
        unit.model_changed = False
    return result


def _prepare_manual_topology_save(topology: dict, project_id: str, *, actor: str):
    """Persist the user's physical channels with the canvas in one request unit."""
    from .physical_ports import materialize_physical_ports
    previous_topology = WorkflowStatusService(project_id).get().get('topology')
    result = _sync_topology_with_invalidation(topology, project_id)
    logical_bindings = {str(port["topology_port_id"]): port for node in result.get("nodes", [])
        for port in node.get("interfaces", []) if port.get("object_type") != "HardwareNetworkInterface"}
    linked = _topology_with_engineering_links(topology, result)
    workflow = WorkflowStatusService(project_id)
    state = workflow.get()
    try:
        physical, changes = materialize_physical_ports(linked,
            all_pages(list_objects, "HardwareNode"), all_pages(list_objects, "HardwareNetworkInterface"),
            state["parameters"].get("networks") or [], prune_unconnected=False, previous_topology=previous_topology,
            routes=all_pages(list_routes), messages=all_pages(list_objects, "Message"))
    except ValueError as error:
        raise EngineeringValidationError(str(error)) from error
    networks = list(state["parameters"].get("networks") or [])
    networks.extend(change["data"] for change in changes if change["object_type"] == "Network")
    if networks != state["parameters"].get("networks", []):
        workflow.save_parameters({**state["parameters"], "networks": networks}, actor=actor)
    resolved = {}
    def resolve(value):
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return resolved.get(value, value) if isinstance(value, str) else value
    for change in changes:
        if change["object_type"] == "Network":
            continue
        data = resolve(change["data"])
        if change.get("action") == "UPDATE":
            saved = update_object(change["object_type"], change["object_id"], data)
        else:
            saved = create_object(change["object_type"], data)
        resolved["$" + change["local_ref"]] = str(saved["id"])
    logical_ports = {str(port["id"]): port for node in linked["nodes"] for port in node.get("ports") or []}
    for node in physical["nodes"]:
        for port in node.get("ports") or []:
            for key in ("engineeringId", "hardwareInterfaceId"):
                port[key] = resolved.get(port.get(key), port.get(key))
            previous = logical_ports.get(str(port["id"]), {})
            if previous.get("engineeringId") and previous.get("engineeringId") != previous.get("hardwareInterfaceId"):
                port["engineeringId"] = previous["engineeringId"]
    if physical != linked or changes:
        # Reconcile connection endpoints with the just-created canonical HWIs.
        result = _sync_topology_with_invalidation({**physical, "topology_id": topology.get("topology_id") or "studio-network"}, project_id)
        for node in result.get("nodes", []):
            for port in node.get("interfaces", []):
                previous = logical_bindings.get(str(port["topology_port_id"]))
                if previous:
                    physical_port = next((p for n in physical['nodes'] for p in n.get('ports', []) if p['id'] == port['topology_port_id']), {})
                    keys = ("engineering_id", "object_type") if physical_port.get('nameSource') == 'network' else ("engineering_id", "engineering_name", "object_type")
                    port.update({key: previous[key] for key in keys if key in previous})
        physical = _topology_with_engineering_links(physical, result)
    return physical, result


def _synchronize_network_routes_with_workflow(
    project_id: str,
    topology: dict,
    *,
    actor: str,
):
    """Synchronize route revisions and immediately publish their real source status.

    ``save_topology`` invalidates routing before the route records are reconciled.
    Without this second transition, already approved and still valid routes remain
    marked OUTDATED in the workflow and block Capacity & Timing even though the
    routing repository is fully synchronized.
    """
    workflow = WorkflowStatusService(project_id)
    result = synchronize_network_routes(project_id, topology, actor=actor)
    workflow.refresh_source_status(
        "routing",
        actor=actor,
        reason="Routing-Tabelle wurde mit der physischen Netzwerktopologie synchronisiert.",
    )
    return result


@engineering_api.route("/topology/sync", methods=["POST"])
def sync_topology_route():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    project_id = _project_id()
    check_edit_token(payload.get("expected_token"), WorkflowStatusService(project_id).get()["topology"])
    if payload.get("persist_workflow", True) is not False:
        topology, result = _prepare_manual_topology_save(payload, project_id, actor=str(payload.get("actor") or "network-editor"))
        WorkflowStatusService(project_id).save_topology(
            topology,
            actor=str(payload.get("actor") or "network-editor"),
        )
        result["routing_sync"] = _synchronize_network_routes_with_workflow(
            project_id,
            topology,
            actor=str(payload.get("actor") or "network-editor"),
        )
        _auto_recalculate_capacity(project_id)
    else:
        result = _sync_topology_with_invalidation(payload, project_id)
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
    state = WorkflowStatusService(_project_id()).get(
        summary=request.args.get("view", "").strip().lower() == "summary"
    )
    return _budgeted_json("workflow_state_response", state)


@engineering_api.route("/workflow/revision", methods=["GET"])
def workflow_revision_route():
    with get_connection() as connection:
        row = connection.execute(
            "SELECT project_id, active_step, versions, parameters, topology FROM engineering_workflow_projects WHERE project_id = %s",
            (_project_id(),),
        ).fetchone()
    if row is None:
        return jsonify({"project_id": _project_id(), "versions": {}, "edit_tokens": {}})
    state = WorkflowStatusService._state(row)
    return jsonify({key: state[key] for key in ("project_id", "versions", "edit_tokens")})


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


@engineering_api.route('/workflow/communication-repair/preview', methods=['POST'])
def preview_communication_repair():
    from .agent_tools.repair_execution import prepare, inspect
    workload_id = _routing_payload().get('workload_id')
    return jsonify(inspect(workload_id) if workload_id else prepare({'defer_review': True}))


@engineering_api.route('/workflow/communication-repair/review', methods=['POST'])
def review_communication_repair():
    from .agent_tools.repair_execution import review_saved
    return jsonify(review_saved({'workload_id': _routing_payload().get('workload_id')}))


@engineering_api.route('/workflow/communication-repair/apply', methods=['POST'])
def apply_communication_repair():
    from .agent_tools import repair_execution
    from .agent_tools.audit import record
    from uuid import uuid4
    payload = _routing_payload()
    workload_id = payload.get('workload_id')
    if not payload.get('choices'):
        from .communication_repair import apply_repair
        return jsonify(apply_repair({'token': payload.get('token'), 'choices': {}}))
    if not workload_id:
        from .communication_repair import load_plan, public_plan, complete_plan
        planner, _ = load_plan()
        workload_id = repair_execution.store_plan(public_plan(complete_plan(planner)))['workload_id']
    repair_execution.authorize(workload_id, payload.get('token'), payload.get('choices'))
    result = repair_execution.resume({'workload_id': workload_id})
    record(str(uuid4()), 'human-repair-choice', 'TOOL_CALL', 'continue_communication_repair', 'SUCCESS',
           {'workload_id': workload_id, 'applied': result['applied']})
    return jsonify(result)


@engineering_api.route("/workflow/parameters", methods=["PATCH"])
def update_workflow_parameters_route():
    payload = _routing_payload()
    parameters = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else payload
    if not parameters:
        raise EngineeringValidationError("parameters muss ein nicht-leeres Objekt sein.")
    project_id = _project_id()
    check_edit_token(payload.get("expected_token"), WorkflowStatusService(project_id).get()["parameters"])
    WorkflowStatusService(project_id).save_parameters(parameters, actor=payload.get("actor"))
    _auto_recalculate_capacity(project_id)
    return jsonify(WorkflowStatusService(project_id).get())


@engineering_api.route("/workflow/simulation-scope", methods=["PATCH"])
def update_simulation_scope_route():
    from .simulation_scope import normalize_simulation_scope
    from .simulation_coverage import simulation_coverage

    payload = _routing_payload()
    scope = normalize_simulation_scope(payload.get("simulation_scope"), require_reason=True)
    coverage = simulation_coverage(all_pages(list_objects, "Message"), all_pages(list_objects, "Signal"), [], scope)
    if coverage["errors"]:
        raise EngineeringValidationError(" ".join(coverage["errors"]))
    project_id = _project_id()
    workflow = WorkflowStatusService(project_id)
    state = workflow.get()
    if normalize_simulation_scope(state["parameters"].get("simulation_scope")) == scope:
        return jsonify(state)
    workflow.save_parameters({**state["parameters"], "simulation_scope": scope}, actor=payload.get("actor") or "simulation-scope")
    _auto_recalculate_capacity(project_id)
    return jsonify(workflow.get())


@engineering_api.route("/workflow/topology", methods=["GET"])
def workflow_topology_route():
    state = WorkflowStatusService(_project_id()).get()
    return jsonify({"project_id": state["project_id"], "topology": state["topology"]})


@engineering_api.route("/workflow/topology", methods=["PUT"])
def update_workflow_topology_route():
    payload = _routing_payload()
    topology = payload.get("topology") if isinstance(payload.get("topology"), dict) else payload
    if not isinstance(topology.get("nodes"), list):
        raise EngineeringValidationError("topology.nodes muss eine Liste sein.")
    project_id = _project_id()
    actor = str(payload.get("actor") or "network-editor")
    workflow = WorkflowStatusService(project_id)
    current_state = workflow.get()
    check_edit_token(payload.get("expected_token"), current_state["topology"])
    physical_complete = current_state.get("artifact_checks", {}).get("network_editor", {}).get("complete", False)
    if current_state["topology"] == topology and physical_complete:
        current_state = workflow.save_topology(topology, actor=actor)
        current_state["routing_sync"] = {
            "counts": {"created": 0, "outdated": 0, "unchanged": 0, "skipped": 0},
            "skipped": [],
        }
        return jsonify(current_state)
    if is_topology_layout_only_change(current_state["topology"], topology) and physical_complete:
        state = workflow.save_topology(topology, actor=actor)
        state["routing_sync"] = {
            "counts": {"created": 0, "outdated": 0, "unchanged": 0, "skipped": 0},
            "skipped": [],
        }
        return jsonify(state)
    from .topology_removal import detached_topology, retire_removed_connections
    topology = detached_topology(current_state['topology'], topology)
    topology, sync_result = _prepare_manual_topology_save(topology, project_id, actor=actor)
    retire_removed_connections(current_state['topology'], topology, actor=actor)
    workflow.save_topology(topology, actor=actor)
    routing_sync = _synchronize_network_routes_with_workflow(
        project_id,
        topology,
        actor=actor,
    )
    _auto_recalculate_capacity(project_id)
    state = workflow.get()
    state["routing_sync"] = routing_sync
    return jsonify(state)


@engineering_api.route("/workflow/bus-technology/preview", methods=["POST"])
def preview_bus_technology_route():
    from .bus_migration import load_bus_change
    payload = _routing_payload()
    plan = load_bus_change(WorkflowStatusService(_project_id()).get(), str(payload.get('network_id') or ''), payload.get('bus'))
    return jsonify(plan['preview'])


@engineering_api.route("/workflow/bus-technology", methods=["PUT"])
def update_bus_technology_route():
    from .bus_migration import load_bus_change
    from .routing.network_sync import enrich_route_from_linked_topology, BUS_PROTOCOLS
    payload = _routing_payload()
    project_id, actor = _project_id(), 'network-editor-bus-change'
    workflow = WorkflowStatusService(project_id)
    current = workflow.get()
    check_edit_token(payload.get('expected_token'), current['topology'])
    plan = load_bus_change(current, str(payload.get('network_id') or ''), payload.get('bus'))
    if payload.get('plan_token') != plan['preview']['token']:
        raise WorkflowConflictError('Das Modell wurde seit der Vorschau geändert. Bitte den Bustyp erneut auswählen.')
    topology = plan['topology']
    patch = payload.get('edge') or {}
    edge = next((e for e in topology['edges'] if e['id'] == patch.get('id')), None)
    if edge is None or edge.get('physicalNetworkId') != payload['network_id']:
        raise EngineeringValidationError('Die bearbeitete Verbindung gehört nicht zum gewählten Bus.')
    original_edge = next(e for e in current['topology']['edges'] if e['id'] == edge['id'])
    for field in ('name', 'sourceInterfaceName', 'targetInterfaceName', 'relationType', 'description', 'direction'):
        if field in patch:
            if field in {'sourceInterfaceName', 'targetInterfaceName'} and patch[field] == original_edge.get(field):
                continue
            edge[field] = patch[field]
    for kind, identifier, change in plan['changes']:
        update_object(kind, identifier, {**change, 'modified_by': actor})
    for node in topology['nodes']:
        for port in node.get('ports', []):
            for side in ('source', 'target'):
                if node['id'] == edge[side] and port['id'] == edge[side + 'Port']:
                    port['name'] = edge.get(side + 'InterfaceName') or port['name']
                    for link in topology['edges']:
                        for endpoint in ('source', 'target'):
                            if link[endpoint] == node['id'] and link[endpoint + 'Port'] == port['id']:
                                link[endpoint + 'InterfaceName'] = port['name']
                    if port.get('hardwareInterfaceId'):
                        update_object('HardwareNetworkInterface', port['hardwareInterfaceId'], {'name': port['name']})
    workflow.save_parameters({**current['parameters'], 'networks': plan['networks']}, actor=actor)
    topology, _ = _prepare_manual_topology_save(topology, project_id, actor=actor)
    workflow.mark_changed('engineering_model', 'Bustyp und kanonische Transportbindungen geändert.', actor=actor)
    affected = {n['id'] for n in plan['preview']['networks']}
    for route in plan['routes']:
        enriched = enrich_route_from_linked_topology(route, topology)
        for endpoint in [enriched['source'], *enriched['destinations']]:
            if endpoint.get('network_id') in affected:
                endpoint['protocol'] = BUS_PROTOCOLS[payload['bus']]
        update_route(str(route['id']), {'source': enriched['source'], 'destinations': enriched['destinations'],
                     'expected_revision': route['revision'], 'modified_by': actor, 'reason': 'Physischer Bustyp geändert.'})
        for link in topology['edges']:
            metadata = (link.get('routingMetadata') or {}).get(str(route['id']))
            if metadata:
                metadata.update(protocol=enriched['source'].get('protocol'), approvalState='PENDING')
    workflow.save_topology(topology, actor=actor)
    validator = RoutingValidator(project_id)
    for route in plan['routes']:
        identifier = str(route['id'])
        saved = get_route(identifier)
        save_validation(identifier, validator.validate(saved, exclude_route_id=identifier), actor=actor)
    workflow.refresh_source_status('routing', actor=actor, reason='Geänderte Busrouten sind erneut zu prüfen und freizugeben.')
    state = workflow.get()
    state['bus_change'] = plan['preview']
    return jsonify(state)


@engineering_api.route('/workflow/bus-name', methods=['PUT'])
def update_bus_name_route():
    payload = _routing_payload()
    try:
        return jsonify(WorkflowStatusService(_project_id()).rename_network(
            str(payload.get('network_id') or ''), payload.get('name'),
            expected_token=payload.get('expected_token'), expected_parameters_token=payload.get('expected_parameters_token')))
    except ValueError as error:
        raise EngineeringValidationError(str(error)) from error


@engineering_api.route('/workflow/ethernet-names', methods=['PUT'])
def normalize_ethernet_names_route():
    payload = _routing_payload()
    try:
        return jsonify(WorkflowStatusService(_project_id()).normalize_ethernet_names(
            expected_token=payload.get('expected_token'), expected_parameters_token=payload.get('expected_parameters_token')))
    except ValueError as error:
        raise EngineeringValidationError(str(error)) from error


@engineering_api.route("/workflow/network-view", methods=["GET"])
def workflow_network_view_route():
    return jsonify(WorkflowStatusService(_project_id()).network_view())


@engineering_api.route('/workflow/frame-device', methods=['POST'])
def create_frame_device_route():
    from .frame_device import plan_frame_device
    from .network_scene import build_network_scene

    payload = _routing_payload()
    workflow = WorkflowStatusService(_project_id())
    state = workflow.get()
    if not payload.get('expected_token'):
        raise EngineeringValidationError('Die aktuelle Modellversion fehlt. Bitte die Ansicht neu laden.')
    check_edit_token(payload['expected_token'], state['topology'])
    plan = plan_frame_device(state, payload, all_pages(list_objects, 'HardwareNode'))
    actor = 'network-editor-frame'
    hardware = create_object('HardwareNode', {**plan['hardware'], 'created_by': actor})
    plan['node'].update(engineeringId=str(hardware['id']), name=hardware['name'])
    topology = build_network_scene(plan['topology'],
        (state['context'].get('wizard_request') or {}).get('prompt', ''), positions=plan['positions'])
    workflow.mark_changed('engineering_model', 'Neues Gerät im Systemrahmen: Gerätedetails und Kommunikation ergänzen.',
                          status='IN_PROGRESS', actor=actor)
    workflow.save_topology(topology, actor=actor, layout_positions=plan['positions'])
    result = workflow.get()
    result['created_device'] = next(n for n in result['topology']['nodes'] if n['id'] == plan['node']['id'])
    return jsonify(result), 201


@engineering_api.route('/workflow/network-assignment/preview', methods=['POST'])
def preview_network_assignment_route():
    from .network_assignment import load_assignment, assignment_request
    state = WorkflowStatusService(_project_id()).get()
    return jsonify(load_assignment(state, assignment_request(_routing_payload()))['preview'])


@engineering_api.route('/workflow/spatial-zoning/preview', methods=['POST'])
def preview_spatial_zoning_route():
    from .zoning_service import SpatialZoningService
    service = SpatialZoningService(_project_id())
    return jsonify(service.preview(service.plan(_routing_payload().get('driving_side'))))


@engineering_api.route('/workflow/spatial-zoning', methods=['PUT'])
def apply_spatial_zoning_route():
    from .zoning_service import SpatialZoningService
    payload = _routing_payload()
    return jsonify(SpatialZoningService(_project_id()).apply(payload.get('plan_token'), payload.get('driving_side'),
        approve_valid=payload.get('approve_valid') is True))


@engineering_api.route('/workflow/network-assignment', methods=['PUT'])
def apply_network_assignment_route():
    from .network_assignment import load_assignment, assignment_request, confirmed_context
    project_id, actor = _project_id(), 'network-editor-assignment'
    workflow = WorkflowStatusService(project_id)
    payload = _routing_payload()
    state = workflow.get()
    check_edit_token(payload.get('expected_token'), state['topology'])
    plan = load_assignment(state, assignment_request(payload))
    if payload.get('plan_token') != plan['preview']['token']:
        raise WorkflowConflictError('Die Zuordnung wurde seit der Vorschau geändert. Bitte die Vorschau erneut prüfen.')
    resolved = {}
    def resolve(value):
        if isinstance(value, dict):
            return {resolved.get(k, k): resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        return resolved.get(value, value) if isinstance(value, str) else value
    for item in plan['creations']:
        created = create_object(item['object_type'], {**resolve(item['data']), 'created_by': actor})
        resolved[item['local_ref']] = str(created['id'])
    for (kind, identifier), values in plan['changes'].items():
        update_object(kind, identifier, {**resolve(values), 'modified_by': actor})
    for planned in plan['routes']:
        if planned.get('_assignment_new'):
            created = create_route({**resolve(planned), 'origin': 'NETWORK_EDITOR', 'approval_state': 'PENDING',
                                    'review_state': 'UNREVIEWED', 'created_by': actor})
            resolved[planned['id']] = str(created['id'])
    topology = resolve(plan['topology'])
    positions = topology['scene']['manualPositions']
    context = confirmed_context(state, topology, plan)
    with get_connection() as connection:
        connection.execute('UPDATE engineering_workflow_projects SET context = %s::jsonb WHERE project_id = %s',
                           (json.dumps(context, default=str), project_id))
    workflow.save_parameters({**state['parameters'], 'networks': plan['networks']}, actor=actor)
    # Reuse canonical relation synchronization, keeping explicit membership fields.
    result = _sync_topology_with_invalidation(topology, project_id)
    topology = _topology_with_engineering_links(topology, result)
    for planned in plan['routes']:
        route = resolve(planned)
        if not planned.get('_assignment_new'):
            update_route(str(route['id']), {**{k: route[k] for k in ('name', 'source', 'destinations', 'payload', 'route')},
                         'expected_revision': route['revision'], 'modified_by': actor, 'reason': 'Bestätigte System- und Buszuordnung geändert.'})
        # Withdraw obsolete approved graph edges until this revision is approved.
        with get_connection() as connection:
            connection.execute("DELETE FROM engineering_relations WHERE project_id = %s AND "
                "((relation_type = 'ROUTES_TO' AND attributes ->> 'route_id' = %s) OR "
                "(relation_type = 'USES_ROUTE' AND target_type = 'RoutingEntry' AND target_id = %s))",
                (project_id, str(route['id']), str(route['id'])))
    workflow.mark_changed('engineering_model', 'Systemzuordnung, Transportverträge und Busanschlüsse geändert.', actor=actor)
    workflow.save_topology(topology, actor=actor, layout_positions=positions)
    validator = RoutingValidator(project_id)
    validations = []
    for route in plan['routes']:
        identifier = resolve(str(route['id']))
        validation = validator.validate(get_route(identifier), exclude_route_id=identifier)
        if not validation.get('valid'):
            details = '; '.join(error['message'] for error in validation.get('errors', [])[:3])
            raise EngineeringValidationError(f"Zuordnung nicht gespeichert: {route['name']}: {details}")
        save_validation(identifier, validation, actor=actor)
        validations.append({'id': identifier, 'valid': validation.get('valid'), 'errors': validation.get('errors', [])})
    workflow.refresh_source_status('routing', actor=actor, reason='Geänderte Zuordnung: betroffene Routen erneut freigeben.')
    result = workflow.get()
    result['assignment'] = {**plan['preview'], 'validations': validations}
    return jsonify(result)


@engineering_api.route("/workflow/network-view", methods=["PUT"])
def update_workflow_network_view_route():
    payload = _routing_payload()
    positions = payload.get('positions')
    if positions is not None and not isinstance(positions, dict):
        raise EngineeringValidationError('positions muss ein Objekt sein.')
    try:
        return jsonify(WorkflowStatusService(_project_id()).prepare_network_view(
            expected_token=payload.get('expected_token'), positions=positions, reset=payload.get('reset') is True,
            bus_routes=payload.get('bus_routes'), reset_wires=payload.get('reset_wires') is True))
    except (TypeError, ValueError) as error:
        raise EngineeringValidationError(str(error)) from error


@engineering_api.route("/workflow/topology-layout", methods=["GET"])
def workflow_topology_layout_route():
    topology_key = str(request.args.get("topology_key") or "").strip()
    try:
        layout_version = int(request.args.get("layout_version", 1))
        return jsonify(WorkflowStatusService(_project_id()).get_topology_layout(topology_key, layout_version))
    except (TypeError, ValueError) as error:
        raise EngineeringValidationError(str(error)) from error


@engineering_api.route("/workflow/topology-layout", methods=["PUT"])
def update_workflow_topology_layout_route():
    payload = _routing_payload()
    try:
        result = WorkflowStatusService(_project_id()).save_topology_layout(
            str(payload.get("topology_key") or ""),
            int(payload.get("layout_version", 1)),
            payload.get("nodes"),
        )
    except (TypeError, ValueError) as error:
        raise EngineeringValidationError(str(error)) from error
    return jsonify(result)


def _workflow_snapshot_summary(snapshot: dict | None, *, keep_overview: bool = False) -> dict | None:
    if not snapshot:
        return None
    summary = {
        key: snapshot.get(key)
        for key in (
            "id",
            "source_versions",
            "status",
            "is_outdated",
            "outdated_reason",
            "created_at",
        )
        if key in snapshot
    }
    if keep_overview:
        results = snapshot.get("results") if isinstance(snapshot.get("results"), dict) else {}
        overview = results.get("overview") if isinstance(results.get("overview"), dict) else None
        if overview is not None:
            summary["results"] = {"overview": overview}
    return summary


@engineering_api.route("/workflow/snapshots", methods=["GET"])
def workflow_snapshots_route():
    service = WorkflowStatusService(_project_id())
    capacity = service.latest_analysis("capacity_timing", include_outdated=True)
    preflight = service.latest_analysis("preflight", include_outdated=True)
    results_analysis = service.latest_analysis("results_analysis", include_outdated=True)
    payload = {
        "capacity": _workflow_snapshot_summary(capacity, keep_overview=True),
        "preflight": _workflow_snapshot_summary(preflight),
        "results_analysis": _workflow_snapshot_summary(results_analysis),
        "simulations": service.list_simulation_snapshots(),
    }
    return _budgeted_json("simulation_snapshot_list", payload)


@engineering_api.route("/workflow/simulation-snapshots", methods=["POST"])
def create_simulation_snapshot_route():
    payload = _routing_payload()
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise EngineeringValidationError("configuration muss ein Objekt sein.")
    from .simulation import prepare_workflow_simulation_config
    configuration = prepare_workflow_simulation_config(configuration, _project_id())
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


@engineering_api.route("/intelligence/issues/approve", methods=["POST"])
def intelligence_approve_issue_route():
    return jsonify(IntelligenceService(_project_id()).approve_issue(_routing_payload()))


@engineering_api.route("/intelligence/issues/approve-all", methods=["POST"])
def intelligence_approve_all_issues_route():
    payload = _routing_payload()
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise EngineeringValidationError("issues muss eine Liste sein.")
    return jsonify(IntelligenceService(_project_id()).approve_issues(issues))


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


@engineering_api.route("/semantics/concepts", methods=["GET"])
def semantic_concepts_route():
    return jsonify(SemanticClassificationService().concepts())


@engineering_api.route("/semantics/concepts/<concept_id>", methods=["GET"])
def semantic_concept_route(concept_id: str):
    concept = SemanticClassificationService().concept(concept_id)
    if concept is None:
        return jsonify({"error": "Semantisches Konzept nicht gefunden."}), 404
    return jsonify(concept)


@engineering_api.route("/semantics/classify", methods=["POST"])
def semantic_classification_route():
    payload = _routing_payload()
    if not str(payload.get("name") or payload.get("display_name") or payload.get("id") or "").strip():
        raise EngineeringValidationError("name oder display_name ist fuer die Semantikklassifikation erforderlich.")
    return jsonify(SemanticClassificationService().classify(payload))


@engineering_api.route("/ml/models/train", methods=["POST"])
def ml_train_model_route():
    payload = _routing_payload()
    task = str(payload.get("task") or "SIGNAL_SEMANTIC_CLASSIFICATION")
    return jsonify(MLInferenceService().train_task(task))


@engineering_api.route("/ml/classify/signal", methods=["POST"])
def ml_classify_signal_route():
    return jsonify(MLInferenceService().classify_signal(_routing_payload()))


@engineering_api.route("/ml/classify/status", methods=["POST"])
def ml_classify_status_route():
    return jsonify(MLInferenceService().classify_status(_routing_payload()))


@engineering_api.route("/ml/classify/physical", methods=["POST"])
def ml_select_physical_model_route():
    return jsonify(MLInferenceService().select_physical_model(_routing_payload()))


@engineering_api.route("/ml/classify/fault", methods=["POST"])
def ml_classify_fault_route():
    return jsonify(MLInferenceService().classify_fault(_routing_payload()))


@engineering_api.route("/ml/rank/routes", methods=["POST"])
def ml_rank_routes_route():
    payload = _routing_payload()
    routes = payload.get("routes") if isinstance(payload.get("routes"), list) else []
    return jsonify(MLInferenceService().rank_routes(routes))


@engineering_api.route("/ml/score/packing", methods=["POST"])
def ml_score_packing_route():
    return jsonify(MLInferenceService().score_packing(_routing_payload()))


@engineering_api.route("/ml/score/architecture", methods=["POST"])
def ml_score_architecture_route():
    return jsonify(MLInferenceService().score_architecture(_routing_payload()))


@engineering_api.route("/ml/explain/qwen", methods=["POST"])
def ml_explain_for_qwen_route():
    return jsonify(MLInferenceService().explain_for_qwen(_routing_payload()))


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
    context = state.get("context") or {}
    prompt = str(((context.get("agent_wizard_status") or {}).get("agent_prompt")) or "")
    inventory = communication_system_inventory(prompt)
    plan = plan_network_distribution(
        result,
        list_objects("HardwareNode", limit=1000),
        state.get("topology") or {},
        parameters=state.get("parameters") or {},
        allowed_protocols=(context.get("engineering_scope_rules") or {}).get("communication_systems"),
        available_protocol_counts=inventory,
        resource_policy=planning_policy(state),
    )
    proposals = []
    for network in plan.get("networks") or []:
        decision = str(network.get("decision") or "UNRESOLVED_CAPACITY_CONSTRAINT")
        if decision == "SPLIT_CURRENT_TECHNOLOGY":
            summary = (
                f"Überlasteten Zweig {network['network_id']} anhand seiner Pakete auf "
                f"{network['proposed_segments']} {network['protocol']}-Segmente verteilen; "
                f"Prognose maximal {network['projected_max_load_percent']:.2f} %."
                + (f" Tool plant {network['new_resources_required']} zusätzliche Ressourcen ein."
                   if network.get('new_resources_required') else ' Vorhandene freie Segmente werden genutzt.')
            )
            kind = "SPLIT_NETWORK_BRANCH"
        elif decision == "MIGRATE_TECHNOLOGY":
            candidate = next(
                (item for item in network.get("technology_candidates") or []
                 if item.get("protocol") == network.get("selected_protocol")),
                {},
            )
            summary = (
                f"Für {network['network_id']} reicht der freie {network['protocol']}-Bestand nicht aus. "
                f"Auf {network['selected_protocol']} mit {candidate.get('required_segments', 1)} Segment(en) migrieren; "
                "Payload und Ziel-Buslast sind rechnerisch geeignet."
            )
            kind = "MIGRATE_NETWORK_TECHNOLOGY"
        else:
            summary = (
                f"Für {network['network_id']} wurde keine verfügbare Kombination aus Segmentanzahl, "
                "Payload und Technologie innerhalb der Ziel-Buslast gefunden."
            )
            kind = "CAPACITY_CONSTRAINT_REVIEW"
        proposals.append({
            "id": f"OPT-BRANCH-{network['network_id']}",
            "status": "PROPOSAL" if decision != "UNRESOLVED_CAPACITY_CONSTRAINT" else "REVIEW_REQUIRED",
            "kind": kind,
            "target_type": "Network",
            "target_id": network["network_id"],
            "summary": summary,
            "branch_analysis": network,
            "protocol_inventory": plan.get("protocol_inventory") or {},
            "requires_human_approval": True,
        })
    for constraint in plan.get("inventory_constraints") or []:
        proposals.append({
            "id": f"OPT-INVENTORY-{constraint['protocol']}",
            "status": "REVIEW_REQUIRED",
            "kind": "CAPACITY_INVENTORY_REVIEW",
            "target_type": "CommunicationSystemInventory",
            "target_id": constraint["protocol"],
            "summary": (
                f"{constraint['protocol']}: {constraint['used']} Segmente belegt, aber nur "
                f"{constraint['provisioned']} bestätigt. Die Überschreitung um "
                f"{constraint['excess']} Segmente muss konsolidiert oder freigegeben werden."
            ),
            "inventory_constraint": constraint,
            "protocol_inventory": plan.get("protocol_inventory") or {},
            "requires_human_approval": True,
        })
    return jsonify({
        "status": result["status"], "plan_status": plan.get("status"),
        "protocol_inventory": plan.get("protocol_inventory") or {},
        "proposals": proposals, "applied": False,
        "resource_policy": plan.get('resource_policy'),
        "resource_allocation": plan.get('resource_allocation'),
        "decision_rationale": plan.get('decision_rationale'),
    })


@engineering_api.route("/capacity/dimension", methods=["POST"])
def communication_dimension_route():
    from .capacity.sizing_service import CommunicationSizingService
    payload = request.get_json(silent=True) or {}
    return jsonify(CommunicationSizingService(_project_id()).preview(payload.get("policy")))


@engineering_api.route("/capacity/dimension/apply", methods=["POST"])
def communication_dimension_apply_route():
    from .capacity.sizing_service import CommunicationSizingService
    payload = _routing_payload()
    result = CommunicationSizingService(_project_id()).apply(payload.get("source_token"), payload.get("policy"),
        actor=str(payload.get("actor") or "capacity-workbench"), approve_valid=payload.get("approve_valid") is True)
    result["capacity"] = CapacityTimingService(_project_id()).calculate()
    return jsonify(result)


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


@engineering_api.route("/workflow/refresh-project", methods=["POST"])
def refresh_project_route():
    from .project_refresh import refresh_project
    return jsonify(refresh_project())


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


@engineering_api.route("/equipment-assignment-learning/retrieve", methods=["POST"])
def retrieve_equipment_assignment_learning_route():
    return jsonify(EquipmentAssignmentLearningService(_project_id()).retrieve(_routing_payload()))


@engineering_api.route("/equipment-assignment-learning/feedback", methods=["POST"])
def record_equipment_assignment_learning_route():
    return jsonify(EquipmentAssignmentLearningService(_project_id()).record(_routing_payload())), 201


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


@engineering_api.route("/routing/message-scopes", methods=["GET"])
def routing_message_scopes_route():
    from .pagination import all_pages
    from .routing.payload_scope import message_scope
    return jsonify({"items": {str(item["id"]): message_scope(item) for item in all_pages(list_objects, "Message")}})


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
    result = RoutingValidator(project_id=_project_id()).validate_table(routes)
    if not result.get("valid"):
        g.routing_validation_failed = True
    return jsonify(result)


@engineering_api.route("/routing/generate", methods=["POST"])
def generate_routing_route():
    return jsonify(RoutingGenerationService().generate_routes({**_routing_payload(), 'model_review': True})), 201


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
    from .pagination import all_pages
    routes = all_pages(list_routes, approval_state="APPROVED")
    state = WorkflowStatusService(_project_id()).get()
    return jsonify(CommunicationConfigBuilder().build(routes, topology=state["topology"], parameters=state["parameters"]))


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
    from .agent_tools.capabilities import structure_evaluate
    return jsonify(structure_evaluate({'selection': payload.get('selections')})['analysis']), 201


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
    from .agent_tools.capabilities import structure_preview
    return jsonify(structure_preview(payload)), 201


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


@engineering_api.route("/reasoning", methods=["GET", "POST"])
def reasoning_collection():
    from .reasoning.service import ReasoningService
    service = ReasoningService()
    if request.method == "GET":
        return jsonify({"items": service.list(request.args.get("job_id"))})
    return jsonify(_reasoning_call(lambda: service.analyze(_routing_payload()).model_dump(mode="json"))), 201


def _reasoning_call(operation):
    try:
        return operation()
    except ValueError as error:
        raise EngineeringValidationError(str(error)) from error


@engineering_api.get("/reasoning/<reasoning_id>")
def reasoning_result(reasoning_id):
    from .reasoning.service import ReasoningService
    return jsonify(ReasoningService().get(reasoning_id).model_dump(mode="json"))


@engineering_api.post("/reasoning/<reasoning_id>/continue")
def reasoning_continue(reasoning_id):
    from .reasoning.service import ReasoningService
    return jsonify(_reasoning_call(lambda: ReasoningService().continue_analysis(reasoning_id).model_dump(mode="json"))), 201


@engineering_api.post("/reasoning/<reasoning_id>/proposal")
def reasoning_proposal(reasoning_id):
    from .reasoning.service import ReasoningService
    return jsonify(_reasoning_call(lambda: ReasoningService().propose(reasoning_id, _routing_payload().get("action_id")))), 201


@engineering_api.post("/reasoning/compare")
def reasoning_compare():
    from .reasoning.service import ReasoningService
    payload = _routing_payload()
    return jsonify(ReasoningService().compare_runs(payload.get("before_reasoning_id"), payload.get("after_reasoning_id")))


@engineering_api.route("/addressing/policy", methods=["GET", "PATCH"])
def logical_address_policy_route():
    allocator = LogicalNodeAddressAllocator(namespace=request.args.get("namespace") or "PROJECT")
    if request.method == "GET":
        return jsonify(allocator.policy().to_dict())
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(allocator.update_policy(payload, actor=str(payload.get("actor") or "address-policy-editor")))


@engineering_api.route("/addressing/conflicts", methods=["GET"])
def logical_address_conflicts_route():
    allocator = LogicalNodeAddressAllocator(namespace=request.args.get("namespace") or "PROJECT")
    items = allocator.detect_conflicts()
    return jsonify({"items": items, "count": len(items), "findings": allocator.findings()})


@engineering_api.route("/addressing/resolve/<address>", methods=["GET"])
def resolve_logical_address_route(address: str):
    return jsonify(AddressResolutionService(namespace=request.args.get("namespace") or "PROJECT").resolve(address))


@engineering_api.route("/addressing/routes/resolve", methods=["GET"])
def resolve_route_by_logical_address_route():
    source = request.args.get("source")
    destination = request.args.get("destination")
    if not source or not destination:
        return jsonify({"error": "source und destination sind erforderlich."}), 400
    items = AddressResolutionService(namespace=request.args.get("namespace") or "PROJECT").resolve_routes(source, destination)
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/addressing/technology-bindings", methods=["GET", "POST"])
def create_technology_address_binding_route():
    if request.method == "GET":
        clauses = ["project_id=%s"]
        values: list[Any] = [current_project_id()]
        for column, value in (
            ("hardware_node_id", request.args.get("hardware_node_id")),
            ("technology", request.args.get("technology")),
            ("network_ref", request.args.get("network_ref")),
        ):
            if value:
                clauses.append(f"{column}=%s")
                values.append(value.upper() if column == "technology" else value)
        with get_connection() as conn:
            items = conn.execute(
                "SELECT * FROM engineering_technology_address_bindings WHERE " + " AND ".join(clauses) + " ORDER BY technology, technology_address",
                values,
            ).fetchall()
        return jsonify({"items": items, "count": len(items)})
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Ein JSON-Objekt wird erwartet."}), 400
    return jsonify(create_technology_address_binding(payload, actor=str(payload.get("actor") or "technology-binding-editor"))), 201


@engineering_api.route("/addressing/audit", methods=["GET"])
def logical_address_audit_route():
    limit = min(max(int(request.args.get("limit") or 200), 1), 1000)
    with get_connection() as conn:
        items = conn.execute(
            "SELECT * FROM engineering_address_audit WHERE project_id=%s ORDER BY event_id DESC LIMIT %s",
            (current_project_id(), limit),
        ).fetchall()
    return jsonify({"items": items, "count": len(items)})


@engineering_api.route("/hardware-nodes/<object_id>/address", methods=["GET", "PATCH", "DELETE"])
def hardware_node_logical_address_route(object_id: str):
    resolver = AddressResolutionService(namespace=request.args.get("namespace") or "PROJECT")
    allocator = resolver.allocator
    if request.method == "GET":
        return jsonify(resolver.resolve_address(object_id))
    payload = request.get_json(silent=True) or {}
    actor = str(payload.get("actor") or "address-editor")
    if request.method == "DELETE":
        return jsonify(allocator.release_address(object_id, actor=actor))
    if "logical_node_address" not in payload:
        return jsonify({"error": "logical_node_address ist erforderlich."}), 400
    impact = allocator.impact_analysis(object_id, payload["logical_node_address"])
    if not bool(payload.get("confirm")):
        return jsonify({
            "error": "Manuelle Adressänderung muss nach der Impact-Analyse bestätigt werden.",
            "impact": impact,
        }), 409
    return jsonify(allocator.assign_address(
        object_id,
        payload["logical_node_address"],
        assignment_mode="MANUAL",
        actor=actor,
    ))


@engineering_api.route("/hardware-nodes/<object_id>/address/allocate", methods=["POST"])
def allocate_hardware_node_logical_address_route(object_id: str):
    payload = request.get_json(silent=True) or {}
    return jsonify(LogicalNodeAddressAllocator(namespace=str(payload.get("namespace") or "PROJECT")).assign_address(
        object_id,
        assignment_mode="AUTO",
        actor=str(payload.get("actor") or "address-allocator"),
    ))


@engineering_api.route("/hardware-nodes/<object_id>/address/impact", methods=["GET"])
def hardware_node_logical_address_impact_route(object_id: str):
    return jsonify(LogicalNodeAddressAllocator(namespace=request.args.get("namespace") or "PROJECT").impact_analysis(
        object_id, request.args.get("address")
    ))


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
