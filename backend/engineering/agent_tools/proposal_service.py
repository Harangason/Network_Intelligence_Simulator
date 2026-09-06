"""Governed proposals in the existing proposal store; no second model store.

Caller owns a project RequestUnit. Approval and apply are separate transactions.
References to earlier changes use ``$<local_ref>`` and are resolved only at apply.
"""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.agent_core.api.tool_contract import EngineeringProposal
from ..db import get_connection, ConcurrentUpdateError, check_revision, mark_model_changed
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
    return {**value, "revision": contract["revision"], "approved_by": contract.get("approved_by"),
            "canonical_ids": contract.get("canonical_ids", []), "workload_id": contract.get("workload_id"),
            'replacement_proposal_id': contract.get('replacement_proposal_id')}


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
    return envelope(legacy.get_proposal(proposal_id))


def create(proposal_type: str, changes: list[dict], rationale: str, *, assumptions: list[str] | None = None,
           evidence: list[dict] | None = None, confidence: float = 0.5, workload_id: str | None = None) -> dict:
    if not changes or len(changes) > 2000:
        raise EngineeringValidationError("Ein Vorschlag benötigt 1 bis 2000 Änderungen.")
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
    row = legacy.create_proposal({"proposal_type": proposal_type, "prompt": rationale,
        "proposed_objects": normalized, "evidence": evidence or [], "confidence": confidence,
        "model": "python-engineering-core", "created_by": "engineering-agent"})
    contract = {"version": 1, "status": "PROPOSED", "revision": str(uuid4()), "changes": normalized,
                "assumptions": assumptions or [], "workload_id": workload_id,
                "object_refs": [{"object_type": c["object_type"], "id": str(c["object_id"])}
                                for c in normalized if c.get("object_id")]}
    return _write(str(row["proposal_id"]), contract)


def _validate_changes(changes: list[dict]) -> dict:
    findings, known, names, definitions = [], {}, set(), {}
    message_signals = {}
    for index, change in enumerate(changes):
        try:
            kind, action = change["object_type"], change["action"]
            data = change.get("data") or {}
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
                result = RoutingValidator().validate(data)
                if not result.get("valid", result.get("is_valid", False)):
                    raise ValueError(f"Route ist nicht gültig: {result.get('findings', result)}")
            elif kind == "Network" and action == "CREATE":
                if not data.get("id") or not data.get("technology"):
                    raise ValueError("Netzwerk benötigt id und technology.")
                from ..routing.validation import PROTOCOL_CAPACITY
                if data["technology"] not in PROTOCOL_CAPACITY:
                    raise ValueError("Unbekannte Netzwerktechnologie.")
                for field in ("bitrate", "arbitration_bitrate", "data_bitrate"):
                    if field in data and (not isinstance(data[field], (int, float)) or data[field] <= 0):
                        raise ValueError(f"{field} muss positiv sein.")
                if any(str(item.get("id")) == str(data["id"]) for item in
                       networks()):
                    raise ValueError("Netzwerk-ID bereits vorhanden.")
            elif kind == "SimulationScenario" and action == "CREATE":
                validate_scenario(data)
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
    if not findings:
        from .validation import validate_effective_model
        findings.extend(validate_effective_model(changes))
    return {"valid": not findings, "requested": len(changes), "valid_count": max(0, len(changes)-len(findings)), "findings": findings}


def validate(proposal_id: str) -> dict:
    row = legacy.get_proposal(proposal_id)
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
    if contract["status"] in {"APPLIED", "REJECTED", "APPROVED"}:
        return envelope(row)
    contract["validation_result"] = _validate_changes(contract["changes"])
    contract["status"] = "VALIDATED" if contract["validation_result"]["valid"] else "PROPOSED"
    contract["base_model_revision"] = model_revision()
    contract["revision"] = str(uuid4())
    return _write(proposal_id, contract, legacy_status="READY_FOR_REVIEW" if contract["status"] == "VALIDATED" else "DRAFT")


def review(proposal_id: str, *, revision: str, decision: str, actor: str, trace_id: str) -> dict:
    """Only called by the human review endpoint; never registered as an MCP tool."""
    row = legacy.get_proposal(proposal_id)
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
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
    contract = deepcopy(row.get("engineering_contract") or {})
    envelope(row)
    if contract["status"] == "APPLIED":
        return envelope(row)
    if contract["status"] != "APPROVED" or not contract.get("approved_by"):
        raise PermissionError("Eine menschliche Freigabe ist erforderlich.")
    if model_revision() != contract["base_model_revision"]:
        contract["status"] = "OUTDATED"
        contract["revision"] = str(uuid4())
        return _write(proposal_id, contract)
    validation = _validate_changes(contract["changes"])
    if not validation["valid"]:
        raise EngineeringValidationError(str(validation["findings"]))
    refs, canonical = {}, []
    for change in contract["changes"]:
        kind, action = change["object_type"], change["action"]
        data = _resolve(change.get("data") or {}, refs)
        if kind in ENTITY_SPECS:
            if action == "CREATE":
                item = create_object(kind, {**data, "source": "ai_generated", "created_by": contract["approved_by"], "review_state": "reviewed", "approval_state": "approved"})
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
        elif kind == "SimulationScenario":
            item = save_scenario({**data, "created_by": contract["approved_by"]})
        elif kind == "Network":
            workflow = WorkflowStatusService(current_project_id())
            parameters = deepcopy(workflow.get()["parameters"])
            parameters.setdefault("networks", []).append(data)
            workflow.save_parameters(parameters, actor=actor)
            item = data
        elif kind == "SignalBehavior":
            from ..signal_behavior_service import save_behavior
            item = save_behavior(data)
        else:
            workflow = WorkflowStatusService(current_project_id())
            parameters = deepcopy(workflow.get()["parameters"])
            item = {**data, "id": str(uuid4()), "proposal_id": proposal_id, "approved_by": contract["approved_by"]}
            parameters.setdefault("engineering_models", {}).setdefault(kind, []).append(item)
            workflow.save_parameters(parameters, actor=actor)
        identifier = str(item.get("id") or item.get("scenario_id"))
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
    if contract.get("workload_id"):
        from ..workloads import EngineeringWorkloadOrchestrator
        EngineeringWorkloadOrchestrator(current_project_id()).evaluate_workload_completion(contract["workload_id"], actor=actor)
    mark_model_changed()
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
