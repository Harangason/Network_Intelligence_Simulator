"""Governed proposals in the existing proposal store; no second model store.

Caller owns a project RequestUnit. Approval and apply are separate transactions.
References to earlier changes use ``$<local_ref>`` and are resolved only at apply.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.agent_core.api.tool_contract import EngineeringProposal
from ..db import get_connection, ConcurrentUpdateError, check_revision, flush_model_changes
from ..project_context import current_project_id
from .. import proposals as legacy
from ..repository import ENTITY_SPECS, get_object, create_object, update_object, delete_object, parent_link_for_payload
from ..models import EngineeringValidationError
from ..routing.validation import RoutingValidator
from ..simulation import save_scenario, validate_scenario
from ..workflow.service import WorkflowStatusService
from .model import model, model_revision, json_safe, networks
from .audit import record

ARTIFACT_TYPES = {"StatusModel", "DataObject", "SignalBehavior"}
MAX_PROPOSAL_CHANGES = 10_000


def order_change_dependencies(changes: list[dict]) -> list[dict]:
    """Use the same nested references for review ordering and sequential apply."""
    from graphlib import TopologicalSorter, CycleError

    def references(value):
        if isinstance(value, str) and value.startswith('$'):
            return {value[1:]}
        if isinstance(value, dict):
            return set().union(*(references(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(references(item) for item in value))
        return set()

    indexed = {change['local_ref']: change for change in changes}
    if len(indexed) != len(changes):
        raise EngineeringValidationError('Doppelte lokale Referenz.')
    dependencies = {key: references(change.get('data') or {}) for key, change in indexed.items()}
    missing = set().union(*dependencies.values()) - indexed.keys()
    if missing:
        raise EngineeringValidationError('Nicht aufgelöste Referenzen: ' + ', '.join(sorted(missing)))
    try:
        return [indexed[key] for key in TopologicalSorter(dependencies).static_order()]
    except CycleError as error:
        raise EngineeringValidationError('Zyklische lokale Referenzen im Vorschlag.') from error


def _write(proposal_id: str, contract: dict, *, legacy_status: str | None = None) -> dict:
    with get_connection() as connection:
        row = connection.execute(
            "UPDATE engineering_ai_proposals SET engineering_contract=%s, "
            "status=COALESCE(%s,status), modified_at=now() WHERE project_id=%s AND proposal_id=%s RETURNING *",
            (Jsonb(json_safe(contract)), legacy_status, current_project_id(), proposal_id),
        ).fetchone()
    return envelope(row)


def envelope(row: dict) -> dict:
    contract = row.get("engineering_contract") or {}
    if not contract:
        raise EngineeringValidationError("Dieser Vorschlag verwendet den bisherigen Review-Ablauf.")
    value = EngineeringProposal(
        proposal_id=str(row["proposal_id"]), proposal_type=row["proposal_type"],
        changes=contract["changes"], object_refs=contract.get("object_refs", []),
        rationale=row["prompt"], assumptions=contract.get("assumptions", []),
        confidence=row.get("confidence") if row.get("confidence") is not None else 0.5,
        evidence=row.get("evidence") or [], validation_result=contract.get("validation_result", {}),
        status=contract["status"],
    ).model_dump(mode="json")
    dependent_results = None
    if contract['status'] == 'APPLIED':
        rate_evidence = next((item for item in row.get('evidence') or []
                              if item.get('source') == 'explicit_network_bitrate'
                              and item.get('engineering_goal_id')), None)
        if rate_evidence:
            from . import conversation
            workload = (conversation.snapshot(current_project_id()).get('engineering_workloads') or {}).get(
                str(rate_evidence['engineering_goal_id'])) or {}
            dependent_results = (workload.get('result') or {}).get('dependent_results')
    return {**value, "revision": contract["revision"], "approved_by": contract.get("approved_by"),
            "canonical_ids": contract.get("canonical_ids", []), "workload_id": contract.get("workload_id"),
            'replacement_proposal_id': contract.get('replacement_proposal_id'),
            **({'dependent_results': dependent_results} if dependent_results else {})}


def set_replacement(proposal_id: str, replacement_id: str):
    row = legacy.get_proposal(proposal_id)
    contract = deepcopy(row['engineering_contract'])
    contract['replacement_proposal_id'] = replacement_id
    return _write(proposal_id, contract)


def latest(proposal_id: str) -> dict:
    for _ in range(20):
        proposal = get(proposal_id)
        if not proposal.get('replacement_proposal_id'):
            return proposal
        proposal_id = proposal['replacement_proposal_id']
    raise ValueError('Zu viele Vorschlagsrevisionen; bitte die aktuelle Fassung öffnen.')


def get(proposal_id: str) -> dict:
    row = legacy.get_proposal(proposal_id)
    result = envelope(row)
    if result['status'] not in {'APPLIED', 'REJECTED'}:
        from .project_draft import assert_proposal_source
        try:
            assert_proposal_source(row)
        except ConcurrentUpdateError as error:
            result['status'] = 'OUTDATED'
            result['validation_result'] = {**result.get('validation_result', {}), 'valid': False,
                'findings': [*result.get('validation_result', {}).get('findings', []),
                             {'severity': 'ERROR', 'code': 'DRAFT_REVISION_CHANGED', 'message': str(error)}]}
    return result


def create(proposal_type: str, changes: list[dict], rationale: str, *, assumptions: list[str] | None = None,
           evidence: list[dict] | None = None, confidence: float = 0.5, workload_id: str | None = None) -> dict:
    if not changes or len(changes) > MAX_PROPOSAL_CHANGES:
        raise EngineeringValidationError(f"Ein Vorschlag benötigt 1 bis {MAX_PROPOSAL_CHANGES} Änderungen.")
    normalized = deepcopy(changes)
    for index, change in enumerate(normalized):
        if change.get("object_type") == "HardwareNode" and (change.get("data") or {}).get("name"):
            from ..repository import normalize_hardware_name
            change["data"]["name"] = normalize_hardware_name(change["data"]["name"])
        change.setdefault("action", "CREATE")
        change.setdefault("local_ref", f"change-{index}")
        if change["action"] in {"UPDATE", "DELETE"} and change.get("object_type") in ENTITY_SPECS:
            target = get_object(change["object_type"], change["object_id"])
            change["expected_version"] = target["version"]
            change["object_name"] = target["name"]
    normalized = order_change_dependencies(normalized)
    row = legacy.create_proposal({"proposal_type": proposal_type, "prompt": rationale,
        "proposed_objects": normalized, "evidence": evidence or [], "confidence": confidence,
        "model": "python-engineering-core", "created_by": "engineering-agent"})
    contract = {"version": 1, "status": "PROPOSED", "revision": str(uuid4()), "changes": normalized,
                "assumptions": assumptions or [], "workload_id": workload_id,
                "object_refs": [{"object_type": c["object_type"], "id": str(c["object_id"])}
                                for c in normalized if c.get("object_id")]}
    return _write(str(row["proposal_id"]), contract)


def _validate_changes(changes: list[dict], *, proposal_type: str = '') -> dict:
    findings, known, names, definitions = [], {}, set(), {}
    message_signals = {}
    route_preview = None
    preview_refs = {}
    if proposal_type == 'PERIODIC_ACQUISITION':
        from .periodic_acquisition import validate_preview
        try:
            snapshot, preview_refs = validate_preview(changes)
            route_preview = RoutingValidator(current_project_id(), model_snapshot=snapshot)
        except (ValueError, KeyError, LookupError) as error:
            return {'valid': False, 'requested': len(changes), 'valid_count': 0,
                    'validation_scope': 'MODEL_STRUCTURE', 'findings': [
                        {'severity': 'ERROR', 'index': 0, 'code': 'ACQUISITION_MODEL_INVALID', 'message': str(error)}]}
    for index, change in enumerate(changes):
        try:
            kind, action = change["object_type"], change["action"]
            data = change.get("data") or {}
            _resolve(data, {key: '$' + key for key in known})
            if action not in {"CREATE", "UPDATE", "DELETE"}:
                raise ValueError("Unbekannte Änderung.")
            ref = change["local_ref"]
            if ref in known:
                raise ValueError("Doppelte lokale Referenz.")
            if kind in ENTITY_SPECS:
                if action == "CREATE":
                    if not str(data.get("name") or "").strip():
                        raise ValueError("Name fehlt.")
                    ENTITY_SPECS[kind].validate(data)
                    parent = parent_link_for_payload(kind, data)
                    if kind == "Interface" and not parent:
                        raise ValueError("Logisches Interface benötigt eine Funktion oder Hardware.")
                    if parent:
                        field, parent_kind, _ = parent
                        value = str(data.get(field) or "")
                        if value.startswith("$"):
                            if known.get(value[1:]) != parent_kind:
                                raise ValueError("Elternreferenz fehlt oder hat den falschen Typ.")
                        else:
                            get_object(parent_kind, value)
                    signature = (kind, str(data.get("name")).casefold(), str(data.get(parent[0])) if parent else "")
                    if signature in names:
                        raise ValueError("Doppeltes Objekt innerhalb des Vorschlags.")
                    names.add(signature)
                else:
                    target = get_object(kind, change["object_id"])
                    check_revision(change.get("expected_version"), target["version"])
                    if action == "UPDATE":
                        ENTITY_SPECS[kind].validate({**target, **data})
                    elif target["lifecycle_state"] != "draft":
                        raise ValueError("Nur Objekte im Lebenszyklus draft dürfen gelöscht werden.")
                    elif not change.get("impact_analysis"):
                        raise ValueError("Löschen benötigt eine dokumentierte Auswirkungsanalyse.")
            elif kind == "RoutingEntry" and action == "CREATE":
                result = (route_preview.validate(_resolve(data, preview_refs), exclude_route_id=preview_refs[ref])
                          if route_preview is not None else RoutingValidator().validate(data))
                if not result.get("valid", result.get("is_valid", False)):
                    issues = result.get('errors') or result.get('findings') or [
                        {'code': 'ROUTING_INVALID', 'message': 'Der Routingvorschlag ist nicht gültig.'}]
                    for issue in issues:
                        findings.append({'severity': 'ERROR', 'index': index,
                            'code': str(issue.get('code') or 'ROUTING_INVALID'),
                            'message': str(issue.get('message') or 'Der Routingvorschlag ist nicht gültig.'),
                            'object_type': kind, 'object_ref': str(change.get('object_id') or ref),
                            'object_name': str(data.get('name') or ''),
                            'source': data.get('source') or {}, 'destinations': data.get('destinations') or []})
                    continue
            elif proposal_type == 'PERIODIC_ACQUISITION' and kind in {
                    'CommunicationCapability', 'CommunicationController', 'PhysicalPort', 'NetworkConnection'} and action == 'CREATE':
                from ..goal_execution.store import RESOURCE_MODELS
                RESOURCE_MODELS[kind].model_validate(data)
            elif kind == "NetworkTopology" and action == "CREATE":
                topology = data.get("topology") if isinstance(data.get("topology"), dict) else {}
                result = WorkflowStatusService._topology_artifact_check(topology)
                if not result["complete"]:
                    raise ValueError(f"Netzwerktopologie ist unvollständig: {result}")
            elif kind == "Network" and action == "UPDATE":
                if proposal_type != 'NETWORK_BITRATE_UPDATE' or set(data) != {'bitrate'}:
                    raise ValueError('Netzwerkänderungen unterstützen nur den geprüften Bitratenauftrag.')
                declared = (WorkflowStatusService(current_project_id()).get().get('parameters') or {}).get('networks') or []
                target = next((item for item in declared if str(item.get('id')) == str(change.get('object_id'))), None)
                if target is None or str(target.get('technology') or '').upper() != 'LIN':
                    raise ValueError('Das deklarierte LIN-Netz wurde nicht gefunden.')
                from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
                result = DEFAULT_TECHNOLOGY_REGISTRY.validate_parameters('LIN', {'bitrate_bps': data['bitrate']})
                if result['status'] != 'VALID':
                    raise ValueError('LIN TechnologyProfile: ' + str(result['findings']))
            elif kind == "Network" and action == "CREATE":
                if not data.get("id") or not data.get("technology"):
                    raise ValueError("Netzwerk benötigt id und technology.")
                from ..routing.validation import PROTOCOL_CAPACITY
                if data["technology"] not in PROTOCOL_CAPACITY:
                    from ...communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY
                    try:
                        DEFAULT_TECHNOLOGY_REGISTRY.profile(data["technology"])
                    except KeyError as error:
                        raise ValueError("Unbekannte Netzwerktechnologie.") from error
                for field in ("bitrate", "arbitration_bitrate", "data_bitrate"):
                    if field in data and (not isinstance(data[field], (int, float)) or data[field] <= 0):
                        raise ValueError(f"{field} muss positiv sein.")
                if any(str(item.get("id")) == str(data["id"]) for item in
                       networks()):
                    raise ValueError("Netzwerk-ID bereits vorhanden.")
            elif kind == "ProjectBundleRestore" and action == "CREATE":
                from .project_bundle_restore import source
                source(data)
            elif kind == "SimulationScenario" and action == "CREATE":
                snapshot = model()
                # Technical preview only. No approval is persisted here.
                validate_scenario({**data, 'faults': [{**fault, 'approved': True}
                    for fault in data.get('faults') or []]},
                    {**snapshot, 'nodes': snapshot['hardware'], 'routes': snapshot['routing']})
            elif kind in ARTIFACT_TYPES and action == "CREATE":
                if not data.get("name"):
                    raise ValueError("Modell benötigt einen Namen.")
                if kind == "StatusModel" and not data.get("states"):
                    raise ValueError("Statusmodell benötigt Zustände.")
                if kind == "DataObject" and not data.get("fields"):
                    raise ValueError("Datenobjekt benötigt Felder.")
                if kind == "SignalBehavior":
                    from ..signal_behavior_service import validate_behavior
                    validate_behavior(data)
            else:
                raise ValueError(f"Änderung wird nicht unterstützt: {action} {kind}")
            known[ref] = kind
            definitions[ref] = data
        except (KeyError, ValueError, LookupError, EngineeringValidationError, ConcurrentUpdateError) as error:
            findings.append({"severity": "ERROR", "index": index, "message": str(error)})
    if not findings and proposal_type == 'HARDWARE_CHANNEL':
        from .hardware_channel import validate_changes
        try:
            validate_changes(changes)
        except (ValueError, KeyError, EngineeringValidationError) as error:
            findings.append({'severity': 'ERROR', 'index': 0, 'code': 'HARDWARE_CHANNEL_INVALID', 'message': str(error)})
    if not findings and proposal_type == 'SIGNAL_RECIPIENT_REPAIR':
        from .repair_execution import validate_recipient_changes
        try:
            validate_recipient_changes(changes)
        except (ValueError, KeyError, EngineeringValidationError) as error:
            findings.append({'severity': 'ERROR', 'index': 0, 'code': 'RECIPIENT_REPAIR_INVALID', 'message': str(error)})
    open_findings = []
    if not findings:
        from .validation import validate_effective_model
        for finding in validate_effective_model(changes):
            # An unassigned communication technology must not prevent a
            # reviewable structural project model. The missing controller
            # status remains explicit and still blocks communication release
            # and preflight. Only this narrow structural proposal may defer it.
            if finding.get('code') == 'CAPACITY_UNVERIFIED':
                # A draft may preserve missing rate evidence for review. This
                # validates its structure, never its communication capacity;
                # capacity/preflight retain their independent evidence gate.
                open_findings.append({**finding, 'severity': 'OPEN'})
            elif (proposal_type == 'SIMPLE_PROJECT_STRUCTURE'
                    and finding.get('code') == 'DEVICE_STATUS_MISSING'
                    and any(change.get('object_type') == 'HardwareNode'
                            and '$' + change.get('local_ref', '') == finding.get('object_id')
                            and not any(item.get('object_type') in {'Interface', 'HardwareNetworkInterface', 'Message'}
                                        for item in changes)
                            for change in changes)):
                open_findings.append({**finding, 'severity': 'OPEN',
                    'message': finding['message'] + ' Kommunikationstechnologie und Statuszyklus sind noch nicht festgelegt.'})
            else:
                findings.append(finding)
    # Several findings on one route still represent one invalid change.
    invalid_count = len({item['index'] for item in findings}) if findings and all('index' in item for item in findings) else len(findings)
    return {"valid": not findings, "requested": len(changes), "valid_count": max(0, len(changes)-invalid_count),
            "validation_scope": "MODEL_STRUCTURE",
            "capacity_status": "UNVERIFIED" if any(item.get('code') == 'CAPACITY_UNVERIFIED'
                for item in open_findings) else "NOT_ASSESSED",
            "findings": [*findings, *open_findings]}


def _validate_topology_inventory(row: dict, changes: list[dict]) -> list[dict]:
    if row.get('proposal_type') not in {'CAPACITY_NETWORK_REPAIR', 'WIZARD_NETWORK_TOPOLOGY'}:
        return []
    from ..intelligence.network_planning import communication_system_inventory, physical_network_inventory
    from ..intelligence.resource_policy import planning_policy, planning_inventory, resource_decision
    state = WorkflowStatusService(current_project_id()).get()
    wizard = (state.get('context') or {}).get('agent_wizard_status') or {}
    inventory = planning_inventory(state)
    policy = planning_policy(state)
    findings = []
    for change in changes:
        if change.get('object_type') != 'NetworkTopology':
            continue
        data = change.get('data') or {}
        topology = data.get('topology') or {}
        counts = physical_network_inventory(topology)
        receipt = data.get('resource_decision')
        receipt_valid = receipt == resource_decision(state.get('topology') or {}, topology, inventory, policy)
        if receipt is not None and not receipt_valid:
            findings.append({'severity': 'ERROR', 'code': 'RESOURCE_DECISION_OUTDATED',
                'message': 'Die Ressourcenentscheidung passt nicht mehr zu Ausgangstopologie, Bestand oder Planungsregeln. Tool-Plan neu erzeugen.'})
        for protocol, networks in counts.items():
            hard_limit = policy['hard_limits'].get(protocol)
            if hard_limit is not None and len(networks) > hard_limit:
                findings.append({'severity': 'ERROR', 'code': 'PHYSICAL_HARD_LIMIT_EXCEEDED',
                    'message': f'{protocol}: {len(networks)} geplante Segmente überschreiten die ausdrücklich feste Grenze {hard_limit}.'})
                continue
            if policy['mode'] == 'AUTO_SIZE' and receipt_valid:
                continue
            maximum = inventory.get(protocol, 0)
            if inventory and len(networks) > maximum:
                findings.append({'severity': 'ERROR', 'code': 'PHYSICAL_INVENTORY_EXCEEDED',
                    'message': f'{protocol}: {len(networks)} physische Segmente geplant, aber nur {maximum} bestätigt. '
                               'Netzverteilung oder verbindlichen Ressourcenbestand fachlich klären.'})
    return findings


def validate(proposal_id: str) -> dict:
    row = legacy.get_proposal(proposal_id)
    from .project_draft import assert_proposal_source
    assert_proposal_source(row)
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
    if contract["status"] in {"APPLIED", "REJECTED", "APPROVED"}:
        return envelope(row)
    contract["validation_result"] = _validate_changes(contract["changes"], proposal_type=row['proposal_type'])
    inventory_findings = _validate_topology_inventory(row, contract['changes'])
    if inventory_findings:
        contract['validation_result']['findings'].extend(inventory_findings)
        contract['validation_result'].update(valid=False, valid_count=0)
    contract["status"] = "VALIDATED" if contract["validation_result"]["valid"] else "PROPOSED"
    contract["base_model_revision"] = model_revision()
    contract["revision"] = str(uuid4())
    return _write(proposal_id, contract, legacy_status="READY_FOR_REVIEW" if contract["status"] == "VALIDATED" else "DRAFT")


def review(proposal_id: str, *, revision: str, decision: str, actor: str, trace_id: str) -> dict:
    """Only called by the human review endpoint; never registered as an MCP tool."""
    row = legacy.get_proposal(proposal_id)
    if decision != 'reject':
        from .project_draft import assert_proposal_source
        assert_proposal_source(row)
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
    if contract.get('replacement_proposal_id') and decision != 'reject':
        raise ConcurrentUpdateError('Dieser Vorschlag wurde durch eine neue Fassung ersetzt. Bitte den aktuellen Vorschlag prüfen.')
    if revision != contract["revision"]:
        raise ConcurrentUpdateError("Der Vorschlag wurde inzwischen geändert.")
    if contract["status"] == "APPLIED":
        return envelope(row)
    if decision == "reject":
        contract["status"] = "REJECTED"
    elif decision == "approve":
        if contract["status"] != "VALIDATED":
            raise EngineeringValidationError("Nur ein validierter Vorschlag kann freigegeben werden.")
        if model_revision() != contract["base_model_revision"]:
            contract["status"] = "OUTDATED"
        else:
            contract.update(status="APPROVED", approved_by=actor, approval_trace_id=trace_id)
    else:
        raise ValueError("Entscheidung muss approve oder reject sein.")
    contract["revision"] = str(uuid4())
    record(trace_id, actor, "HUMAN_REVIEW", "review_proposal", contract["status"], {"proposal_id": proposal_id})
    return _write(proposal_id, contract, legacy_status="REJECTED" if decision == "reject" else None)


def _resolve(value, refs: dict[str, str]):
    if isinstance(value, str) and value.startswith("$"):
        if value[1:] not in refs:
            raise EngineeringValidationError(f"Nicht aufgelöste Referenz: {value}")
        return refs[value[1:]]
    if isinstance(value, dict):
        return {key: _resolve(item, refs) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, refs) for item in value]
    return value


def apply(proposal_id: str, *, actor: str, trace_id: str) -> dict:
    row = legacy.get_proposal(proposal_id)
    from .project_draft import assert_proposal_source
    assert_proposal_source(row)
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
    if contract.get('replacement_proposal_id') and contract['status'] != 'APPLIED':
        raise ConcurrentUpdateError('Dieser Vorschlag wurde ersetzt und kann nicht mehr übernommen werden. Bitte die neue Fassung prüfen.')
    if contract["status"] == "APPLIED":
        return envelope(row)
    if contract["status"] != "APPROVED" or not contract.get("approved_by"):
        raise PermissionError("Eine menschliche Freigabe ist erforderlich.")
    if model_revision() != contract["base_model_revision"]:
        contract["status"] = "OUTDATED"
        contract["revision"] = str(uuid4())
        return _write(proposal_id, contract)
    validation = _validate_changes(contract["changes"], proposal_type=row['proposal_type'])
    inventory_findings = _validate_topology_inventory(row, contract['changes'])
    if inventory_findings:
        validation['findings'].extend(inventory_findings)
        validation['valid'] = False
    if not validation["valid"]:
        raise EngineeringValidationError(str(validation["findings"]))
    refs, canonical = {}, []
    for change in contract["changes"]:
        kind, action = change["object_type"], change["action"]
        data = _resolve(change.get("data") or {}, refs)
        if kind in ENTITY_SPECS:
            if action == "CREATE":
                if row['proposal_type'] == 'STRUCTURE_TRANSFER':
                    # Server-produced transfer evidence, reviewed with the changes,
                    # preserves lineage without accepting governance in object data.
                    for evidence in row.get('evidence') or []:
                        if evidence.get('source') != 'structure_transfer':
                            continue
                        for origin in evidence.get('object_origins') or []:
                            if origin.get('local_ref') == change['local_ref'] and origin.get('object_type') == kind:
                                data['provenance'] = {'origin': 'structure-transfer', 'proposal_id': proposal_id,
                                                      'source_object_id': origin['source_object_id']}
                if row['proposal_type'] == 'MODEL_IMPORT':
                    for evidence in row.get('evidence') or []:
                        if evidence.get('source') != 'engineering_import':
                            continue
                        for origin in evidence.get('object_origins') or []:
                            if origin.get('local_ref') == change['local_ref'] and origin.get('object_type') == kind:
                                data['provenance'] = {'origin': 'engineering-import', 'proposal_id': proposal_id,
                                    'import_id': evidence['import_id'], 'file_name': evidence['file_name'],
                                    'import_key': origin['import_key']}
                item = create_object(kind, {**data, "source": "ai_generated", "created_by": contract["approved_by"], "review_state": "reviewed", "approval_state": "approved"})
                if row['proposal_type'] == 'HARDWARE_CHANNEL':
                    from .hardware_channel import persist_port
                    persist_port(item, contract.get('workload_id'))
            elif action == "UPDATE":
                item = update_object(kind, change["object_id"], {**data, "expected_version": change["expected_version"], "actor": actor})
            else:
                delete_object(kind, change["object_id"])
                item = {"id": change["object_id"], "deleted": True}
        elif kind == "RoutingEntry":
            from ..routing.repository import create_proposal, accept_proposal_routes, save_validation, approve_routes
            route_proposal = create_proposal({"prompt":row["prompt"],"generated_routes":[data],"actor":contract["approved_by"]})
            item = accept_proposal_routes(str(route_proposal["proposal_id"]),[0],actor=contract["approved_by"])[0]
            save_validation(str(item["id"]),RoutingValidator().validate(item,exclude_route_id=str(item["id"])),actor=actor)
            item = approve_routes([str(item["id"])],actor=contract["approved_by"])[0]
        elif row['proposal_type'] == 'PERIODIC_ACQUISITION' and kind in {
                'CommunicationCapability', 'CommunicationController', 'PhysicalPort', 'NetworkConnection'}:
            from ..goal_execution.store import save_resource
            item = save_resource(kind, data)
        elif kind == "NetworkTopology":
            topology = data.get("topology") if isinstance(data.get("topology"), dict) else {}
            flush_model_changes(actor=actor, reason='Freigegebene Hardwarekanäle für die physische Topologie übernommen.')
            WorkflowStatusService(current_project_id()).save_topology(topology, actor=actor)
            from ..routing.network_sync import reconcile_linked_routes
            reconcile_linked_routes(current_project_id(), topology, actor=actor)
            WorkflowStatusService(current_project_id()).refresh_source_status('routing', actor=actor,
                reason='Freigegebene Routen mit den bestätigten physischen Hardwarekanälen geprüft.')
            item = {"id": "workflow-network-topology", "name": data.get("name") or "Netzwerktopologie"}
        elif kind == "ProjectBundleRestore":
            from .project_bundle_restore import restore
            item = restore(data, actor=contract['approved_by'])
        elif kind == "SimulationScenario":
            item = save_scenario({**data, 'source': 'ai_generated',
                'faults': [{**fault, 'source': 'ai_generated', 'approved': True}
                           for fault in data.get('faults') or []],
                "created_by": contract["approved_by"]})
        elif kind == "Network":
            workflow = WorkflowStatusService(current_project_id())
            parameters = deepcopy(workflow.get()["parameters"])
            if action == 'UPDATE':
                target = next((entry for entry in parameters.get('networks', [])
                               if str(entry.get('id')) == str(change['object_id'])), None)
                if target is None:
                    raise ConcurrentUpdateError('Das zu ändernde LIN-Netz wurde entfernt.')
                target.update(data)
                item = target
            else:
                parameters.setdefault("networks", []).append(data)
                item = data
            workflow.save_parameters(parameters, actor=actor)
        elif kind == "SignalBehavior":
            from ..signal_behavior_service import save_behavior
            item = save_behavior(data)
        else:
            workflow = WorkflowStatusService(current_project_id())
            parameters = deepcopy(workflow.get()["parameters"])
            item = {**data, "id": str(uuid4()), "proposal_id": proposal_id, "approved_by": contract["approved_by"]}
            parameters.setdefault("engineering_models", {}).setdefault(kind, []).append(item)
            workflow.save_parameters(parameters, actor=actor)
        identifier = str(item.get("id") or item.get("connection_id") or item.get("scenario_id"))
        refs[change["local_ref"]] = identifier
        canonical.append({"object_type": kind, "id": identifier})
    contract.update(status="APPLIED", canonical_ids=canonical, revision=str(uuid4()))
    # Keep existing workload persistence able to discover approved canonical IDs.
    original = deepcopy(row["proposed_objects"])
    for index, item in enumerate(original):
        if index < len(canonical):
            item["canonical_id"] = canonical[index]["id"]
    with get_connection() as connection:
        connection.execute("UPDATE engineering_ai_proposals SET proposed_objects=%s WHERE proposal_id=%s AND project_id=%s",
                           (Jsonb(json_safe(original)), proposal_id, current_project_id()))
    result = _write(proposal_id, contract, legacy_status="APPROVED")
    # Direct assistant goals live in the conversation, not the legacy workload
    # table. Their canonical completion is reconciled by the apply endpoint.
    if contract.get("workload_id") and row['proposal_type'] not in {'HARDWARE_CHANNEL', 'SIGNAL_RECIPIENT_REPAIR', 'PERIODIC_ACQUISITION'}:
        from ..workloads import EngineeringWorkloadOrchestrator
        EngineeringWorkloadOrchestrator(current_project_id()).evaluate_workload_completion(contract["workload_id"], actor=actor)
    record(trace_id, actor, "APPLY", "apply_approved_proposal", "APPLIED", {"proposal_id": proposal_id, "canonical_ids": canonical})
    return result


def impact(object_type: str, object_id: str) -> dict:
    target = get_object(object_type, object_id)
    snapshot = model()
    from ..relations import list_relations
    relations, offset = [], 0
    while True:
        page = list_relations(limit=500, offset=offset)
        relations.extend(json_safe(page))
        if len(page) < 500:
            break
        offset += len(page)
    snapshot["relations"] = relations
    def references(value, identifiers):
        if isinstance(value, dict):
            return any(references(item, identifiers) for key, item in value.items() if key != "id")
        if isinstance(value, list):
            return any(references(item, identifiers) for item in value)
        return str(value) in identifiers
    affected, visited = [], {str(object_id)}
    while True:
        found = []
        for section, rows in snapshot.items():
            for row in rows if isinstance(rows, list) else []:
                identifier = str(row.get("id") or row.get("relation_id") or "")
                if identifier and identifier not in visited and references(row, visited):
                    found.append({"section": section, "id": identifier, "name": row.get("name")})
        if not found:
            break
        affected.extend(found)
        visited.update(item["id"] for item in found)
    return {"target": json_safe(target), "affected_objects": affected,
            "model_revision": model_revision(),
            "warning": "Direkte und transitive Referenzen einschließlich Beziehungen; Kapazität, Routing und Simulation müssen danach erneut geprüft werden."}
