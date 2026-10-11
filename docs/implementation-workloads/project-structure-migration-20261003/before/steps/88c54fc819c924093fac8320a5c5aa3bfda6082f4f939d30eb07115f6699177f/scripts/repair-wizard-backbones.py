"""Repair the confirmed single-gateway backbone, rollback unless --apply."""
import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engineering.agent_tools import model, wizard_generation, proposal_service
from backend.engineering.db import RequestUnit, close_pool
from backend.engineering.project_context import activate_project, reset_project
from backend.engineering.repository import create_object, update_object
from backend.engineering.workflow.service import WorkflowStatusService

parser = argparse.ArgumentParser()
parser.add_argument('--project', required=True)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
token = activate_project(args.project)
unit = RequestUnit(args.project)
try:
    workflow = WorkflowStatusService(args.project)
    state = workflow.get(summary=True)
    prompt = state['context']['agent_wizard_status']['agent_prompt']
    graph = json.loads(re.search(r'^- Systemcluster-Graph:\s*(\[[^\r\n]*\])', prompt, re.M).group(1))
    controllers = {str(c['ecu']).casefold() for cluster in graph for c in cluster.get('controllers', [])}
    nodes = model.objects('HardwareNode')
    gateways = [n for n in nodes if n['device_type'] == 'Gateway']
    assert len(gateways) == 1, 'Repair requires an unambiguous central gateway.'
    gateway = gateways[0]
    ports = model.objects('HardwareNetworkInterface')
    gateway_ports = [p for p in ports if str(p['hardware_node_id']) == str(gateway['id'])]
    chains = wizard_generation.extract_specification(prompt)['chains']
    backbones = sorted({(c['interface_type'], c['transport_network_ref']) for c in chains
        if c['hardware_name'].casefold() in controllers and c.get('transport_network_ref')})
    changes = []
    for technology, network in backbones:
        assert any(p.get('network_ref') == network and p['technology'] == technology for p in ports)
        if any(p.get('network_ref') == network and p['technology'] == technology for p in gateway_ports):
            continue
        free = next((p for p in gateway_ports if p['technology'] == technology and not p.get('network_ref')), None)
        if free:
            update_object('HardwareNetworkInterface', str(free['id']),
                {'name': network, 'network_ref': network, 'expected_version': free['version']})
            free['network_ref'] = network
            action = 'UPDATE'
        else:
            channel = max((int(p.get('channel_index') or 0) for p in gateway_ports), default=0) + 1
            created = create_object('HardwareNetworkInterface', {'name': network, 'technology': technology,
                'network_ref': network, 'hardware_node_id': str(gateway['id']), 'channel_index': channel,
                'source': 'ai_generated'})
            gateway_ports.append(created)
            action = 'CREATE'
        changes.append({'action': action, 'technology': technology, 'network': network})
    if changes:
        workflow.mark_changed('engineering_model', 'Bestätigte Backbone-Anschlüsse des zentralen Gateways ergänzt.', actor='wizard-backbone-repair')
    proposal = wizard_generation.generate_routing({'prompt': prompt})
    proposal = proposal_service.validate(proposal['proposal_id'])
    report = {'project': args.project, 'applied': args.apply, 'changes': changes,
        'routing_proposal_id': proposal['proposal_id'], 'routing_status': proposal['status'],
        'route_count': len(proposal['changes']), 'validation': proposal['validation_result']}
    print(json.dumps(report, default=str), flush=True)
    if args.apply:
        assert proposal['status'] == 'VALIDATED', 'Do not commit a repair that fails route validation.'
        unit.finish(True)
finally:
    unit.close()
    reset_project(token)
    close_pool()
