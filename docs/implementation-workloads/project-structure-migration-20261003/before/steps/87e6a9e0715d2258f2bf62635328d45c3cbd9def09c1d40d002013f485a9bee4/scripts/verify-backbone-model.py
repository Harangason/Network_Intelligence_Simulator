"""Revalidate transports and rebuild the editor while preserving canonical wiring."""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.db import RequestUnit, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.agent_tools import model, proposal_service, wizard_generation
from backend.engineering.routing.validation import RoutingValidator
from backend.engineering.routing.repository import save_validation
from backend.engineering.workflow.service import WorkflowStatusService
from backend.engineering.physical_ports import topology_port_findings

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
project = 'network-project-20260909082213746-780a13ef'
token = activate_project(project)
unit = RequestUnit(project)
try:
    workflow = WorkflowStatusService(project)
    before = workflow.get()['topology']
    for edge in before['edges']:
        if edge.get('origin') == 'CANONICAL_HISTORY_RESTORATION' and not edge.get('engineeringRelationId'):
            edge['engineeringRelationId'] = edge['id']
    workflow.save_topology(before, actor='backbone-history-repair')
    interfaces = model.objects('HardwareNetworkInterface')
    bindings = {str(p['id']): p.get('network_ref') for p in interfaces}
    findings, invalid = [], []
    for route in model.routes():
        if route.get('status') in ('REJECTED', 'SUPERSEDED', 'OUTDATED'):
            continue
        validation = RoutingValidator().validate(route, exclude_route_id=str(route['id']))
        if not validation['valid']:
            invalid.append({'id': str(route['id']), 'name': route['name'], 'errors': validation['errors']})
            if args.apply:
                save_validation(str(route['id']), validation, actor='backbone-validation')
        findings.extend(validation['errors'])
    if args.apply:
        workflow.mark_changed('routing', reason='Buspfade und Befehlsspezifikationen vollständig neu geprüft', actor='backbone-validation')
    proposal = wizard_generation.generate_network_topology({'prompt': 'Bestätigte physische Busbindungen und sämtliche bestehende Verkabelung erhalten; aktuelle Routenreferenzen synchronisieren.'})
    topology = next(c['data']['topology'] for c in proposal['changes'] if c['object_type'] == 'NetworkTopology')
    old_edges = {(e['source'], e['sourcePort'], e['target'], e['targetPort'], e.get('physicalNetworkId')) for e in before['edges']}
    new_edges = {(e['source'], e['sourcePort'], e['target'], e['targetPort'], e.get('physicalNetworkId')) for e in topology['edges']}
    def undirected(edges):
        return {(frozenset(((a, ap), (b, bp))), net) for a, ap, b, bp, net in edges}
    assert undirected(old_edges) <= undirected(new_edges), 'Previously confirmed wiring disappeared'
    port_changes = [c for c in proposal['changes'] if c['object_type'] == 'HardwareNetworkInterface']

    assert all(c.get('action') == 'UPDATE' and 'network_ref' not in c['data'] for c in port_changes), 'Unexpected bus binding changes'
    proposal = proposal_service.validate(proposal['proposal_id'])
    assert proposal['status'] == 'VALIDATED', proposal.get('validation_result')
    if args.apply:
        proposal = proposal_service.review(proposal['proposal_id'], revision=proposal['revision'], decision='approve', actor='backbone-validation', trace_id=str(uuid4()))
        proposal_service.apply(proposal['proposal_id'], actor='backbone-validation', trace_id=str(uuid4()))
        assert bindings == {str(p['id']): p.get('network_ref') for p in model.objects('HardwareNetworkInterface')}
        assert not topology_port_findings(workflow.get()['topology'], model.objects('HardwareNode'), model.objects('HardwareNetworkInterface'))
        unit.finish(True)
    print(json.dumps({'applied': args.apply, 'invalid_routes': invalid, 'old_edges': len(old_edges), 'new_edges': len(new_edges),
                      'bus_bindings_unchanged': True, 'connector_references_completed': len(port_changes), 'wiring_preserved': True, 'topology_proposal_id': proposal['proposal_id']}, ensure_ascii=False, default=str))
finally:
    unit.close()
    reset_project(token)
    close_pool()
