"""Complete, project-scoped canonical model access for engineering tools."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from backend.nis.infrastructure.persistence.repository import ENTITY_SPECS
from backend.nis.infrastructure.persistence.repository import list_objects
from backend.nis.engineering.relations import list_relations
from backend.nis.engineering.routing.repository import list_routes
from backend.nis.workflow.services.service import WorkflowStatusService
from backend.nis.engineering.projects.project_context import current_project_id

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
    from backend.nis.engineering.goal_execution.store import resources
    state = WorkflowStatusService(current_project_id()).get()
    return {
        "project_id": current_project_id(),
        **{key: objects(kind) for key, kind in SECTIONS.items()},
        "routing": routes(),
        "topology": json_safe(state.get("topology") or {}),
        "parameters": json_safe(state.get("parameters") or {}),
        "behaviors": _behaviors(),
        "communication_resources": resources(),
    }


def _behaviors():
    from backend.nis.engineering.simulation import _list_behaviors
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


class ProjectContext:
    """A frozen identity/revision boundary over actively read canonical data."""
    def __init__(self, project_id, snapshot):
        from copy import deepcopy
        self.project_id = project_id
        self._snapshot = deepcopy(snapshot)
        self.revision = hashlib.sha256(json.dumps(self._snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def snapshot(self):
        from copy import deepcopy
        return deepcopy(self._snapshot)


class ProjectRepository:
    """OOP adapter over the existing project-scoped DB owner; no second registry."""
    def __init__(self, project_id=None):
        self.project_id = project_id or current_project_id()

    def _check_scope(self):
        if self.project_id != current_project_id():
            raise ValueError('Project context differs from the active database scope.')

    def get(self, kind, identifier):
        self._check_scope()
        from backend.nis.infrastructure.persistence.repository import get_object
        return json_safe(get_object(kind, str(identifier)))

    def context(self):
        self._check_scope()
        return ProjectContext(self.project_id, model())

    def function_context(self, signal_id):
        output = self.get('Signal', signal_id)
        message = self.get('Message', output['message_id'])
        interface = self.get('Interface', message['interface_id'])
        if not interface.get('function_id'):
            raise ValueError('Output must belong to an explicit canonical function.')
        function = self.get('Function', interface['function_id'])
        hardware = self.get('HardwareNode', function['hardware_node_id'])
        if hardware.get('device_class') not in (3, 4):
            raise ValueError('QWEN executable function proposals require a class 3/4 device.')
        context = self.context()
        snapshot = context.snapshot()
        hardware_id = str(hardware['id'])
        message_ids = {str(row['id']) for row in snapshot['messages'] if hardware_id in [str(ref) for ref in
            ((row.get('configuration') or {}).get('transport_unit') or {}).get('consumer_refs', [])]}
        routed_ids = set()
        for route in snapshot['routing']:
            if any(str(destination.get('node_id')) == hardware_id for destination in route.get('destinations') or []):
                routed_ids.update(str(ref) for ref in (route.get('payload') or {}).get('signal_ids') or [])
        inputs = [row for row in snapshot['signals'] if str(row.get('message_id')) in message_ids
                  or str(row['id']) in routed_ids]
        return {'project_id':self.project_id, 'model_revision':context.revision,
            'output':output, 'message':message, 'interface':interface, 'function':function,
            'hardware':hardware, 'candidate_inputs':inputs,
            'routing':snapshot['routing'], 'parameters':snapshot['parameters'],
            'requirements':(function.get('configuration') or {}).get('requirements'),
            'unresolved':'Missing bindings/requirements/parameters must be explicit; class alone defines no behavior'}
