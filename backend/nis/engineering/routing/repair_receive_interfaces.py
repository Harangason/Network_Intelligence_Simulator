"""Preview or atomically repair uniquely determined, stale receive references.

Run with ``python -m backend.nis.engineering.routing.repair_receive_interfaces
--project PROJECT``; review the JSON, then supply its token with ``--apply TOKEN``.
Canonical writes retain audit history and require renewed approval.
"""
from __future__ import annotations

# Direct file entrypoints resolve the installed/source package independently of cwd.
import sys as _cli_sys
from pathlib import Path as _CliPath
_cli_backend = next(p for p in _CliPath(__file__).resolve().parents if p.name == "backend")
_cli_sys.path.insert(0, str(_cli_backend.parent))

import argparse
import hashlib
import json

from backend.nis.infrastructure.persistence.db import RequestUnit
from backend.nis.engineering.pagination import all_pages
from backend.nis.engineering.projects.project_context import activate_project
from backend.nis.engineering.projects.project_context import current_project_id
from backend.nis.engineering.projects.project_context import reset_project
from backend.nis.infrastructure.persistence.repository import list_objects
from backend.nis.workflow.services.service import WorkflowStatusService
from backend.nis.engineering.routing.endpoint_consistency import align_receive_interfaces
from backend.nis.engineering.routing.repository import list_routes
from backend.nis.engineering.routing.repository import update_route
from backend.nis.engineering.routing.repository import save_validation
from backend.nis.engineering.routing.validation import RoutingValidator


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
    from backend.nis.infrastructure.persistence.db import close_pool
    try:
        print(json.dumps(run(args.project, args.apply), default=str, ensure_ascii=False))
    finally:
        close_pool()
