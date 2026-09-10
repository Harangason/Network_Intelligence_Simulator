"""Preview or atomically repair uniquely determined, stale receive references.

Run with ``python -m backend.engineering.routing.repair_receive_interfaces
--project PROJECT``; review the JSON, then supply its token with ``--apply TOKEN``.
Canonical writes retain audit history and require renewed approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from ..db import RequestUnit
from ..pagination import all_pages
from ..project_context import activate_project, current_project_id, reset_project
from ..repository import list_objects
from ..workflow.service import WorkflowStatusService
from .endpoint_consistency import align_receive_interfaces
from .repository import list_routes, update_route, save_validation
from .validation import RoutingValidator


def run(project: str, apply_token: str | None = None) -> dict:
    context = activate_project(project)
    unit = RequestUnit(current_project_id())
    try:
        unit.acquire()
        interfaces = all_pages(list_objects, 'Interface')
        ports = all_pages(list_objects, 'HardwareNetworkInterface')
        routes = all_pages(list_routes)
        changes = []
        for route in routes:
            if route['status'] in {'REJECTED', 'OUTDATED', 'SUPERSEDED', 'DEPRECATED'}:
                continue
            candidate = align_receive_interfaces(route, interfaces, ports)
            if candidate['destinations'] != route['destinations']:
                changes.append({'before': route, 'destinations': candidate['destinations']})
        fingerprint = json.dumps([current_project_id(), changes, interfaces, ports], sort_keys=True, default=str)
        token = hashlib.sha256(fingerprint.encode()).hexdigest()
        report = {'project': current_project_id(), 'token': token, 'count': len(changes), 'applied': False, 'changes': changes}
        if apply_token:
            if token != apply_token:
                raise RuntimeError('The reviewed repair plan is stale; create and review a new preview.')
            actor = 'routing-consistency-repair'
            validator = RoutingValidator(current_project_id())
            for change in changes:
                before = change['before']
                route_id = str(before['id'])
                saved = update_route(route_id, {
                    'destinations': change['destinations'], 'expected_revision': before['revision'],
                    'modified_by': actor,
                    'reason': 'Veraltete logische Empfängerschnittstelle nach Bustypwechsel an den bestehenden physischen Anschluss angepasst.',
                })
                validation = validator.validate(saved, exclude_route_id=route_id)
                if not validation['valid']:
                    raise RuntimeError(f"Repair of {before['route_code']} remains invalid: {validation['errors']}")
                change['after'] = save_validation(route_id, validation, actor=actor)
            if changes:
                workflow = WorkflowStatusService(current_project_id())
                workflow.mark_changed('routing', 'Logische Empfängerbindungen korrigiert; erneute Freigabe erforderlich.', actor=actor)
            unit.finish(True)
            report['applied'] = True
        return report
    finally:
        unit.close()
        reset_project(context)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--apply', metavar='REVIEWED_TOKEN')
    args = parser.parse_args()
    from ..db import close_pool
    try:
        print(json.dumps(run(args.project, args.apply), default=str, ensure_ascii=False))
    finally:
        close_pool()
