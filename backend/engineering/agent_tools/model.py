"""Complete, project-scoped canonical model access for engineering tools."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from ..repository import ENTITY_SPECS, list_objects
from ..relations import list_relations
from ..routing.repository import list_routes
from ..workflow.service import WorkflowStatusService
from ..project_context import current_project_id

SECTIONS = {
    "hardware": "HardwareNode", "functions": "Function",
    "interfaces": "Interface", "hardware-interfaces": "HardwareNetworkInterface",
    "signals": "Signal", "messages": "Message",
}


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def objects(object_type: str) -> list[dict[str, Any]]:
    if object_type not in ENTITY_SPECS:
        raise ValueError(f"Unbekannter Objekttyp: {object_type}")
    rows, offset = [], 0
    while True:
        page = list_objects(object_type, limit=500, offset=offset)
        rows.extend(page)
        if len(page) < 500:
            return json_safe(rows)
        offset += len(page)


def routes() -> list[dict[str, Any]]:
    rows, offset = [], 0
    while True:
        page = list_routes(limit=500, offset=offset)
        rows.extend(page)
        if len(page) < 500:
            return json_safe(rows)
        offset += len(page)


def model() -> dict[str, Any]:
    state = WorkflowStatusService(current_project_id()).get()
    return {
        "project_id": current_project_id(),
        **{key: objects(kind) for key, kind in SECTIONS.items()},
        "routing": routes(),
        "topology": json_safe(state.get("topology") or {}),
        "parameters": json_safe(state.get("parameters") or {}),
        "behaviors": _behaviors(),
    }


def _behaviors():
    from ..simulation import _list_behaviors
    return json_safe(_list_behaviors())


def networks() -> list[dict[str, Any]]:
    state = WorkflowStatusService(current_project_id()).get()
    declared = {str(item["id"]): json_safe(item) for item in state["parameters"].get("networks", [])}
    for route in routes():
        source = route.get("source") or {}
        identifier = str(source.get("network_id") or "")
        if identifier:
            declared.setdefault(identifier,{"id":identifier,"name":identifier,"technology":source.get("protocol","CUSTOM"),"source":"canonical_route"})
    return list(declared.values())


def model_revision() -> str:
    # Proposal validation/approval timestamps are deliberately excluded. Every
    # canonical object version, route and parameter/topology value is included.
    snapshot = model()
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
