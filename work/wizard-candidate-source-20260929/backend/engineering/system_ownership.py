"""Persist confirmed system membership independently of physical connectivity.

The migration is deliberately a dry run by default. It only resolves exact,
unique canonical names from accepted project evidence, preserving explicit edits.
"""
from __future__ import annotations

from typing import Any
from copy import deepcopy

from .structure_rules import normalize_hardware_name
from .pagination import all_pages


def confirmed_system_owner_plan(hardware: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> dict[str, Any]:
    by_name: dict[str, list[dict]] = {}
    for node in hardware:
        if node.get("lifecycle_state") == "superseded":
            continue
        by_name.setdefault(normalize_hardware_name(str(node.get("name") or "")).casefold(), []).append(node)
    latest: dict[str, dict] = {}
    for entry in sorted(feedback, key=lambda row: str(row.get("recorded_at") or "")):
        name = normalize_hardware_name(str(entry.get("endpoint_name") or "")).casefold()
        if name:
            latest[name] = entry
    changes, skipped = [], []
    for name, entry in latest.items():
        if entry.get("accepted") is not True:
            continue
        endpoints = by_name.get(name, [])
        owners = by_name.get(normalize_hardware_name(str(entry.get("controller_name") or "")).casefold(), [])
        if len(endpoints) != 1 or len(owners) != 1:
            skipped.append({"endpoint_name": entry.get("endpoint_name"), "reason": "Name fehlt oder ist nicht eindeutig"})
            continue
        endpoint, owner = endpoints[0], owners[0]
        if endpoint["id"] == owner["id"] or owner.get("device_type") in {"SensorController", "ActuatorController", "Gateway"}:
            skipped.append({"endpoint_name": endpoint["name"], "reason": "Ungültiger System-Eigentümer"})
            continue
        identity = endpoint.get("identity") or {}
        existing = identity.get("system_owner_id") or identity.get("systemOwnerId")
        if existing:
            if str(existing) != str(owner["id"]):
                skipped.append({"endpoint_name": endpoint["name"], "reason": "Explizite Zuordnung bleibt erhalten", "existing_owner_id": str(existing)})
            continue
        changes.append({
            "id": str(endpoint["id"]), "name": endpoint["name"], "expected_version": endpoint["version"],
            "owner_id": str(owner["id"]), "owner_name": owner["name"],
            "identity": {**identity, "system_owner_id": str(owner["id"]), "system_owner_source": "wizard-confirmed",
                         "system_owner_evidence": {key: entry[key] for key in ("source", "recorded_at", "endpoint_name", "controller_name") if key in entry}},
        })
    return {"changes": changes, "skipped": skipped, "count": len(changes)}


def migrate_confirmed_system_owners(project_id: str, *, apply: bool = False, actor: str = "system-ownership-migration") -> dict[str, Any]:
    """Review or atomically apply the current project's exact confirmed matches."""
    from .db import RequestUnit
    from .project_context import activate_project, current_project_id, reset_project
    from .repository import list_objects, update_object
    from .workflow.service import WorkflowStatusService

    token = activate_project(project_id)
    unit = RequestUnit(current_project_id())
    try:
        state = WorkflowStatusService(current_project_id()).get()
        hardware = all_pages(list_objects, "HardwareNode")
        plan = confirmed_system_owner_plan(
            hardware,
            (state.get("context") or {}).get("equipment_assignment_feedback") or [],
        )
        identities = {str(item["id"]): item.get("identity") or {} for item in hardware}
        identities.update({change["id"]: change["identity"] for change in plan["changes"]})
        topology = deepcopy(state.get("topology") or {})
        topology_changes = []
        for node in topology.get("nodes", []):
            identity = identities.get(str(node.get("engineeringId") or node.get("id")), {})
            owner_id = identity.get("system_owner_id") or identity.get("systemOwnerId")
            if not owner_id or str(owner_id) not in identities:
                continue
            source = str(identity.get("system_owner_source") or "explicit")
            if node.get("systemOwnerId") != str(owner_id) or node.get("systemOwnerSource") != source:
                node.update(systemOwnerId=str(owner_id), systemOwnerSource=source)
                topology_changes.append({"node_id": node["id"], "owner_id": str(owner_id)})
        if apply:
            for change in plan["changes"]:
                update_object("HardwareNode", change["id"], {
                    "identity": change["identity"], "expected_version": change["expected_version"],
                    "actor": actor, "change_summary": f"Bestätigte Systemzuordnung: {change['owner_name']}",
                })
            if plan["changes"]:
                WorkflowStatusService(current_project_id()).mark_changed("engineering_model", reason="Bestätigte Systemzuordnungen übernommen", actor=actor)
            if topology_changes:
                WorkflowStatusService(current_project_id()).save_topology(topology, actor=actor)
            unit.finish(True)
        return {"project_id": current_project_id(), "applied": apply, "topology_changes": topology_changes, **plan}
    finally:
        unit.close()
        reset_project(token)
