"""Idempotent transport backfill from explicit project evidence only."""
from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from .simulation_coverage import active_rows, simulation_coverage
from .system_ownership import confirmed_system_owner_plan


def route_keys(routes: list[dict], signals: list[dict]) -> set[tuple[str, str, str]]:
    parents = {str(row["id"]): str(row.get("message_id") or "") for row in signals}
    keys = set()
    for route in active_rows(routes):
        payload = route.get("payload") or {}
        messages = set(str(item) for item in payload.get("message_ids") or [])
        if payload.get("message_id"):
            messages.add(str(payload["message_id"]))
        messages.update(parents.get(str(item), "") for item in payload.get("signal_ids") or [])
        source = str((route.get("source") or {}).get("node_id") or "")
        for destination in route.get("destinations") or []:
            target = str(destination.get("node_id") or "")
            keys.update((source, target, message) for message in messages if source and target and message)
    return keys


def confirmed_route_candidates(hardware, interfaces, messages, signals, routes, feedback):
    nodes = {str(row["id"]): row for row in active_rows(hardware)}
    owners = {str(row["id"]): str((row.get("identity") or {}).get("system_owner_id") or
                                 (row.get("identity") or {}).get("systemOwnerId") or "") for row in nodes.values()}
    confirmed = confirmed_system_owner_plan(list(nodes.values()), feedback)
    owners.update({row["id"]: row["owner_id"] for row in confirmed["changes"]})
    interface_nodes = {str(row["id"]): str(row.get("hardware_node_id") or "") for row in interfaces}
    existing = route_keys(routes, signals)
    accepted_routes = [row for row in active_rows(routes) if row.get("approval_state") == "APPROVED" and (row.get("validation") or {}).get("valid")]
    endpoint_types = {"SensorController", "ActuatorController"}
    hmi = {}
    for route in accepted_routes:
        source = str((route.get("source") or {}).get("node_id") or "")
        if nodes.get(source, {}).get("device_type") in endpoint_types | {"Gateway"}:
            continue
        for destination in route.get("destinations") or []:
            target = str(destination.get("node_id") or "")
            if target in nodes and nodes[target].get("device_type") not in endpoint_types:
                hmi.setdefault((source, target), route)
    candidates, unconfirmed = [], []
    for message in active_rows(messages):
        if str(message.get("direction") or "tx").casefold() not in {"tx", "bidirectional"}:
            continue
        message_id = str(message["id"])
        source = interface_nodes.get(str(message.get("interface_id") or ""), "")
        if source not in nodes:
            unconfirmed.append({"message_id": message_id, "name": message.get("name"), "reason": "Quellgerät fehlt"})
            continue
        consumer_refs = {str(item) for item in ((message.get("configuration") or {}).get("transport_unit") or {}).get("consumer_refs") or []}
        targets = {target: {"source": "message-consumer-ref"} for target in consumer_refs if target in nodes}
        if nodes[source].get("device_type") in endpoint_types:
            owner = owners.get(source)
            if owner in nodes and nodes[owner].get("device_type") not in endpoint_types | {"Gateway"} and (not consumer_refs or owner in consumer_refs):
                targets[owner] = {"source": "confirmed-system-owner", "owner_id": owner}
        for (sender, target), template in hmi.items():
            same_interface = str((template.get("source") or {}).get("interface_id") or "") == str(message.get("interface_id") or "")
            if sender == source and (target in consumer_refs or (not consumer_refs and same_interface)):
                targets[target] = {"source": "existing-approved-controller-route", "route_id": str(template["id"])}
        if not targets and not any(key[0] == source and key[2] == message_id for key in existing):
            unconfirmed.append({"message_id": message_id, "name": message.get("name"), "source_id": source,
                                "source_name": nodes[source]["name"], "reason": "Kein bestätigter Empfänger oder Transportbedarf"})
        for target, evidence in sorted(targets.items()):
            key = (source, target, message_id)
            if target != source and key not in existing:
                candidates.append({"source_id": source, "target_id": target, "message_id": message_id,
                    "source_name": nodes[source]["name"], "target_name": nodes[target]["name"], "message_name": message["name"],
                    "evidence": evidence, "template": hmi.get((source, target))})
                existing.add(key)
    return {"candidates": candidates, "unconfirmed_messages": unconfirmed, "ownership_skipped": confirmed["skipped"]}


def repair_confirmed_routes(project_id: str, *, apply: bool = False, actor: str = "confirmed-routing-repair") -> dict:
    from .db import RequestUnit
    from .project_context import activate_project, current_project_id, reset_project
    from .agent_tools import model, proposal_service
    from .routing.generation import RoutingGenerationService
    from .routing.validation import RoutingValidator
    from .workflow.service import WorkflowStatusService

    token = activate_project(project_id)
    unit = RequestUnit(current_project_id())
    try:
        workflow = WorkflowStatusService(current_project_id())
        state = workflow.get()
        hardware, interfaces = model.objects("HardwareNode"), model.objects("Interface")
        messages, signals, routes = model.objects("Message"), model.objects("Signal"), model.routes()
        plan = confirmed_route_candidates(hardware, interfaces, messages, signals, routes,
            (state.get("context") or {}).get("equipment_assignment_feedback") or [])
        valid_routes = [row for row in active_rows(routes) if row.get("approval_state") == "APPROVED" and (row.get("validation") or {}).get("valid")]
        report = {"project_id": current_project_id(), "applied": False, "before": simulation_coverage(messages, signals, valid_routes),
                  "unconfirmed_messages": plan["unconfirmed_messages"], "ownership_skipped": plan["ownership_skipped"],
                  "changes": [], "invalid": [], "existing_route_count": len(active_rows(routes))}
        changes = []
        for candidate in plan["candidates"]:
            route = RoutingGenerationService().generate_route(source_node_id=candidate["source_id"],
                destination_node_id=candidate["target_id"], message_id=candidate["message_id"])
            template = candidate.pop("template", None)
            # Preserve only already approved gateway evidence for this pair;
            # never choose the first arbitrary gateway as an invented path.
            if (template and (template.get("route") or {}).get("gateways")
                    and (template.get("source") or {}).get("interface_id") == route["source"].get("interface_id")
                    and (template.get("source") or {}).get("protocol") == route["source"].get("protocol")):
                route["route"] = {**route.get("route", {}), **deepcopy(template["route"])}
            route["description"] = "Fehlender Transport aus bestätigter Projektzuordnung ergänzt."
            validation = RoutingValidator().validate(route)
            if not validation.get("valid"):
                report["invalid"].append({**candidate, "validation": validation})
                continue
            route["validation"] = validation
            changes.append({"object_type": "RoutingEntry", "data": route})
            report["changes"].append(candidate)
        report["new_route_count"] = len(changes)
        report["projected_after"] = simulation_coverage(messages, signals, valid_routes + [change["data"] for change in changes])
        if apply and changes:
            proposal = proposal_service.create("WIZARD_ROUTING", changes,
                f"{len(changes)} fehlende bestätigte Transporte ergänzen; bestehende Routen bleiben erhalten.",
                evidence=[{"source": "confirmed-routing-backfill", "assignments": report["changes"]}],
                assumptions=["Fehlende Empfänger ohne explizite Projektbelege bleiben als offene Anforderung erhalten."])
            proposal = proposal_service.validate(proposal["proposal_id"])
            if proposal["status"] != "VALIDATED":
                raise ValueError(f"Routing-Reparatur nicht valide: {proposal.get('validation_result')}")
            proposal = proposal_service.review(proposal["proposal_id"], revision=proposal["revision"], decision="approve", actor=actor, trace_id=str(uuid4()))
            applied = proposal_service.apply(proposal["proposal_id"], actor=actor, trace_id=str(uuid4()))
            workflow.mark_changed("routing", reason="Bestätigte fehlende Transporte ergänzt", actor=actor)
            report["proposal_id"] = applied["proposal_id"]
            report["canonical_ids"] = applied["canonical_ids"]
            report["after"] = simulation_coverage(messages, signals, [row for row in model.routes()
                if row.get("approval_state") == "APPROVED" and (row.get("validation") or {}).get("valid")])
            unit.finish(True)
            report["applied"] = True
        return report
    finally:
        unit.close()
        reset_project(token)


def refresh_confirmed_topology(project_id: str, *, apply: bool = False, actor: str = "confirmed-routing-repair") -> dict:
    """Reconcile reviewed physical channels after backfill, then rerun analyses."""
    from .db import RequestUnit
    from .project_context import activate_project, current_project_id, reset_project
    from .agent_tools import model, proposal_service, wizard_generation
    from .workflow.service import WorkflowStatusService
    from .capacity.service import CapacityTimingService, PreflightService
    from .intelligence.service import IntelligenceService

    token = activate_project(project_id)
    unit = RequestUnit(current_project_id())
    try:
        workflow = WorkflowStatusService(current_project_id())
        before = workflow.get()
        owners_before = {str(item["id"]): deepcopy(item.get("identity") or {}) for item in model.objects("HardwareNode")}
        interfaces_before = {str(item["id"]) for item in model.objects("HardwareNetworkInterface")}
        proposal = wizard_generation.generate_network_topology({"prompt": "Vorhandene bestätigte physische Kanäle und Netze erhalten; Routing-Zuordnungen aus dem aktuellen kanonischen Bestand aktualisieren."})
        proposal = proposal_service.validate(proposal["proposal_id"])
        if proposal["status"] not in {"VALIDATED", "APPLIED"}:
            raise ValueError(f"Topologie-Reparatur nicht valide: {proposal.get('validation_result')}")
        topology = next(change["data"]["topology"] for change in proposal["changes"] if change["object_type"] == "NetworkTopology")
        report = {"project_id": current_project_id(), "applied": False, "proposal_id": proposal["proposal_id"],
                  "nodes": len(topology["nodes"]), "edges": len(topology["edges"]),
                  "linked_routes": len({str(item) for edge in topology["edges"] for item in edge.get("routingEntryIds") or []}),
                  "new_physical_channels": sum(change["object_type"] == "HardwareNetworkInterface" and change.get("action", "CREATE") == "CREATE" for change in proposal["changes"]),
                  "validation": proposal.get("validation_result")}
        if not apply:
            return report
        if proposal["status"] != "APPLIED":
            approved = proposal_service.review(proposal["proposal_id"], revision=proposal["revision"], decision="approve", actor=actor, trace_id=str(uuid4()))
            applied = proposal_service.apply(approved["proposal_id"], actor=actor, trace_id=str(uuid4()))
            if applied["status"] != "APPLIED":
                raise ValueError(f"Topologie-Reparatur wurde nicht übernommen: {applied['status']}")
        owners_after = {str(item["id"]): item.get("identity") or {} for item in model.objects("HardwareNode")}
        if owners_after != owners_before:
            raise ValueError("Topologie-Aktualisierung würde kanonische Systemeigentümer verändern.")
        if not interfaces_before.issubset({str(item["id"]) for item in model.objects("HardwareNetworkInterface")}):
            raise ValueError("Topologie-Aktualisierung würde vorhandene physische Kanäle entfernen.")
        if workflow.get()["parameters"].get("simulation_scope") != before["parameters"].get("simulation_scope"):
            raise ValueError("Topologie-Aktualisierung würde den Simulationsumfang verändern.")
        capacity = CapacityTimingService(current_project_id()).calculate()
        preflight = PreflightService(current_project_id()).run()
        intelligence = IntelligenceService(current_project_id()).assess()
        report.update(applied=True, capacity_status=capacity.get("status"), preflight_status=preflight.get("status"),
                      preflight_findings=preflight.get("findings"), intelligence_status=intelligence.get("status"),
                      workflow_statuses=workflow.get(summary=True)["statuses"])
        unit.finish(True)
        return report
    finally:
        unit.close()
        reset_project(token)
