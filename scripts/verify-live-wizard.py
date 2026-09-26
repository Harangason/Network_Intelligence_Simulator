"""Real HTTP acceptance through the UI proxy, in an isolated test project.

Explicit review/apply requests are confined to the newly created test project.
No LLM stub, simulation stub, or direct database writes are used.
"""
from __future__ import annotations
import argparse
from http.cookiejar import CookieJar
import json
import hashlib
import os
import re
from pathlib import Path
import time
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlsplit
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:13500')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--prompt-file', type=Path, help='Replay a real wizard specification in an isolated project.')
    parser.add_argument('--project-id', help='Continue a newly created isolated draft, before canonical model generation.')
    parser.add_argument('--initial-can-fd-segments', type=int)
    parser.add_argument('--technology', choices=['can_fd', 'ethernet'], default='can_fd')
    parser.add_argument('--complete-scope', action='store_true', help='Confirm consumers for both ECU status messages, so ALL is executable.')
    args = parser.parse_args()
    endpoint = urlsplit(args.base_url)
    if (os.environ.get('NIS_E2E_ISOLATED') != '1' or endpoint.hostname not in {'127.0.0.1', 'localhost'}
            or endpoint.port in {None, 13500, 15050}):
        raise SystemExit('Use run-release-gate.py. HTTP acceptance refuses the product stack.')
    expected_steps = {'engineering_model', 'routing', 'network_editor', 'parameters', 'capacity_timing',
                      'validation', 'simulation', 'results_analysis', 'data_science_intelligence'}
    if args.project_id and not args.project_id.startswith('nis-e2e-'):
        raise SystemExit('Existing-project acceptance requires a nis-e2e- test project.')
    project = args.project_id or 'astra-e2e-' + uuid4().hex[:12]
    print(json.dumps({'phase': 'start', 'project': project}), flush=True)
    run_id = str(uuid4())
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    evidence = []

    def request(path, payload=None, headers=None, stream=False):
        started = time.monotonic()
        req = Request(args.base_url + path, method='GET' if payload is None else 'POST',
                      headers={'X-Project-ID': project, 'Content-Type': 'application/json', **(headers or {})},
                      data=None if payload is None else json.dumps(payload).encode())
        with opener.open(req, timeout=180) as response:
            result = [json.loads(line) for line in response if line.strip()] if stream else json.load(response)
            evidence.append({'path': path, 'method': req.method, 'status': response.status,
                             'seconds': round(time.monotonic() - started, 3)})
        return result

    prompt = f'''Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: {run_id}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {{"gateways":1,"ecus":1,"sensors":1,"actuators":1}}
- Aktor-Befehle: {{"MotorValve":{{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{{"semantic_type":"BOOLEAN"}},"data":{{"enum_values":{{"CLOSE":0,"OPEN":1}}}}}}}}
- Systemcluster-Graph: [{{"cluster_id":"drive","label":"Motor","network_id":"can_fd","network_label":"CAN-FD","bus_name":"Drive","controllers":[{{"ecu":"Motorsteuerung","sensors":["MotorTemperature"],"actuators":["MotorValve"]}}]}}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge das isolierte Testnetz mit einem Gateway, einer Motorsteuerung, einem Temperatursensor und einem Stellglied.
'''
    applied = []
    if args.complete_scope:
        prompt = prompt.replace('"ecus":1', '"ecus":2')
        lines = prompt.splitlines()
        graph_index = next(i for i, line in enumerate(lines) if line.startswith('- Systemcluster-Graph:'))
        graph = json.loads(lines[graph_index].split(': ', 1)[1])
        graph[0]['controllers'].append({'ecu': 'Anzeige', 'sensors': [], 'actuators': []})
        graph[0]['hmi_routes'] = [{'source': 'Motorsteuerung', 'target': 'Anzeige'},
                                {'source': 'Anzeige', 'target': 'Motorsteuerung'},
                                {'source': 'System', 'target': 'Anzeige'}]
        lines[graph_index] = '- Systemcluster-Graph: ' + json.dumps(graph)
        prompt = '\n'.join(lines).replace('einer Motorsteuerung, einem Temperatursensor',
            'einer Motorsteuerung, einer Anzeige, einem Temperatursensor')
    if args.technology == 'ethernet':
        prompt = prompt.replace('CAN-FD', 'Ethernet').replace('can_fd', 'ethernet')
    rate_lines = 'Ethernet: 100 Mbit/s' if args.technology == 'ethernet' else (
        'CAN-FD: 500 kbit/s arbitration, 2 Mbit/s data\nCAN: 500 kbit/s'
    )
    prompt = prompt.replace('- Hardware-Sollwerte:', rate_lines + '\n- Hardware-Sollwerte:', 1)
    if args.initial_can_fd_segments is not None:
        assert args.initial_can_fd_segments >= 0
        prompt = prompt.replace('- Hardware-Sollwerte:',
            '- Kommunikationssystem-Sollwerte: ' + json.dumps([{'id': 'can_fd', 'count': args.initial_can_fd_segments}])
            + '\n- Hardware-Sollwerte:')
    resource_decisions = []
    warning_approvals = []
    wizard_context = {'scope_ids': sorted(expected_steps), 'project_name': 'Isolated HTTP acceptance',
                      'mode': 'full', 'process_ids': ['defaults', 'review_gate', 'approve_after_allow']}
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding='utf-8')
        prompt = re.sub(r'^- Lauf-ID:.*$', '- Lauf-ID: ' + run_id, prompt, flags=re.M)
        metadata = args.prompt_file.with_suffix('.json')
        if metadata.exists():
            wizard_context.update(json.loads(metadata.read_text(encoding='utf-8')).get('wizard_context') or {})
    wizard_context.update(project_id=project, run_id=run_id)
    request_revision = None
    for attempt in range(8):
        message = prompt + ('\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.' if attempt else '')
        command = {'action': 'CONTINUE' if attempt else 'START', 'run_id': run_id,
                   'operation_id': str(uuid4()), 'target': 'data_science_intelligence'}
        if not attempt:
            command['wizard_context'] = wizard_context
        if request_revision is not None:
            command['request_revision'] = request_revision
        events = request('/api/engineering/agent/chat', {'prompt': message, 'wizard_command': command}, stream=True)
        receipts = [event.get('wizard_receipt') for event in events if event.get('wizard_receipt')]
        if receipts:
            request_revision = receipts[-1]['request_revision']
        proposals = [event['proposal'] for event in events if event.get('type') == 'APPROVAL' and event.get('proposal')]
        if not proposals:
            deadline = time.monotonic() + 600
            while True:
                workflow = request('/api/engineering/workflow?view=summary')
                assert set(workflow['statuses']) == expected_steps, workflow['statuses']
                if all(value in {'COMPLETE', 'APPROVED', 'WARNING'} for value in workflow['statuses'].values()):
                    break
                execution = workflow.get('context', {}).get('agent_execution') or {}
                if execution.get('state') == 'REVIEW_REQUIRED':
                    conversation = request('/api/engineering/agent/conversation')['data']
                    candidate = conversation.get('active_proposal')
                    if candidate:
                        proposal = request('/api/engineering/agent/proposals/' + candidate)['data']
                        if proposal['status'] not in {'APPLIED', 'REJECTED'}:
                            proposals = [proposal]
                            break
                if execution.get('state') == 'READY_TO_CONTINUE':
                    break
                if execution.get('state') == 'BLOCKED' and 'READY_WITH_WARNINGS' in execution.get('message', ''):
                    preflight = request('/api/engineering/preflight')
                    assert preflight['results']['preflight_status'] == 'READY_WITH_WARNINGS', preflight['results']
                    assert preflight['id'] not in warning_approvals, 'The same warning snapshot blocked continuation twice.'
                    approval = request('/api/engineering/preflight/warnings/approve', {
                        'snapshot_id': preflight['id'], 'actor': 'isolated-http-acceptance',
                    })
                    assert approval['preflight']['ready_for_simulation'], approval['preflight']
                    warning_approvals.append(preflight['id'])
                    break
                assert execution.get('state') not in {'BLOCKED', 'FAILED', 'INCOMPLETE'}, {
                    'statuses': workflow['statuses'], 'execution': execution, 'events': events[-5:]}
                assert time.monotonic() < deadline, {'reason': 'Background workflow timed out', 'execution': execution}
                time.sleep(.5)
            if not proposals:
                if all(value in {'COMPLETE', 'APPROVED', 'WARNING'} for value in workflow['statuses'].values()):
                    break
                continue
        for proposal in proposals:
            assert proposal['status'] == 'VALIDATED', proposal.get('validation_result')
            if proposal['proposal_type'] in {'WIZARD_NETWORK_TOPOLOGY', 'CAPACITY_NETWORK_REPAIR'}:
                receipt = next(change['data']['resource_decision'] for change in proposal['changes']
                               if change['object_type'] == 'NetworkTopology')
                assert receipt['decision_maker'] == 'deterministic-network-planner'
                if args.initial_can_fd_segments == 0:
                    assert any(item['increase_over_baseline'] > 0 for item in receipt['resources'])
                    assert 'Tool-Entscheidung:' in proposal['rationale']
                resource_decisions.append(receipt)
            if proposal['proposal_type'] == 'WIZARD_ENGINEERING_MODEL' and not args.prompt_file:
                names = {change['data']['name'] for change in proposal['changes'] if change['object_type'] == 'HardwareNode'}
                assert {'Motorsteuerung', 'MotorTemperature', 'MotorValve'} <= names, names
            token = request('/api/engineering/agent/review-session')['csrf_token']
            intent = {'X-Review-CSRF': token, 'X-Human-Review': 'confirmed'}
            base = '/api/engineering/agent/proposals/' + proposal['proposal_id']
            approved = request(base + '/review', {'decision': 'approve', 'revision': proposal['revision']}, intent)
            assert approved['success'] and approved['data']['status'] == 'APPROVED', approved
            result = request(base + '/apply?view=status', {'revision': approved['data']['revision']}, intent)
            assert result['success'] and result['data']['status'] == 'APPLIED', result
            applied.append({'id': proposal['proposal_id'], 'type': proposal['proposal_type'],
                            'canonical_objects': len(result['data']['canonical_ids'])})
    else:
        raise AssertionError('Wizard did not finish within eight review boundaries.')
    jobs = request('/api/simulations')['jobs']
    completed = next(job for job in jobs if job['status'] == 'completed')
    snapshots = request('/api/engineering/workflow/snapshots')
    snapshot = next(item for item in snapshots['simulations'] if item.get('job_id') == completed['id'])
    full_snapshot = request('/api/engineering/workflow/simulation-snapshots/' + snapshot['id'])
    assessment = (full_snapshot.get('result') or {}).get('assessment')
    if args.complete_scope or args.prompt_file:
        assert assessment and assessment['scope_coverage']['complete'], assessment
        assert assessment['scope_coverage']['scope_mode'] == 'ALL', assessment
        assert not assessment['missing_observed_signal_ids'], assessment
        assert not assessment['missing_observed_route_ids'], assessment
        assert not assessment['missing_observed_network_ids'], assessment
        assert assessment['conformance'] == 'PASS', assessment
        assert assessment['failed_route_count'] == 0, assessment
    print(json.dumps({'phase': 'simulation', 'project': project, 'job_id': completed['id'], 'artifacts': (completed.get('result') or {}).get('artifacts')}), flush=True)
    trace = request('/api/simulations/' + completed['id'] + '/trace-window?limit=5')
    assert trace['count'] > 0 and any(event.get('signals') for event in trace['events']), {
        'count': trace['count'], 'signal_events': sum(bool(event.get('signals')) for event in trace['events'])}
    repeated = request('/api/engineering/agent/chat', {'prompt': '', 'wizard_command': {
        'action': 'CONTINUE', 'run_id': run_id, 'operation_id': str(uuid4()),
        **({'request_revision': request_revision} if request_revision is not None else {}),
    }}, stream=True)
    assert any(event.get('type') == 'RESULT' and event.get('status') == 'COMPLETED' for event in repeated), repeated[-3:]
    assert len(request('/api/simulations')['jobs']) == len(jobs), 'Retry created a duplicate simulation.'
    network_view = request('/api/engineering/workflow/network-view')
    topology = network_view['topology']
    scene = topology.get('scene') or {}
    assert scene.get('version', 0) >= 2 and scene.get('buses'), 'Wizard did not persist the complete network scene.'
    semantic_nodes = [{k: v for k, v in node.items() if k not in {'x', 'y', 'width', 'height', 'ports'}} | {
        'ports': [{k: v for k, v in port.items() if k not in {'side', 'offset'}} for port in node.get('ports', [])]
    } for node in topology['nodes']]
    signature = hashlib.sha256(json.dumps({'nodes': semantic_nodes, 'edges': topology['edges']},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert scene['modelSignature'] == signature, 'Saved scene does not match canonical topology.'
    ports = {(node['id'], port['id']): port for node in topology['nodes'] for port in node.get('ports', [])}
    expected = {(edge[side], edge[side + 'Port']) for edge in topology['edges'] for side in ('source', 'target')}
    actual = set()
    for bus in scene['buses']:
        for branch in bus['branches']:
            key = branch['nodeId'], branch['portId']
            assert key not in actual, 'A physical port is drawn on multiple buses.'
            actual.add(key)
            assert ports[key]['physicalNetworkId'] == bus['id'] and ports[key]['bus'] == bus['technology']
        assert bus['participantCount'] == len({branch['nodeId'] for branch in bus['branches']})
    assert actual == expected, 'Saved scene omits or invents physical branches.'
    scene_summary = {'version': scene['version'], 'nodes': len(topology['nodes']), 'buses': len(scene['buses']),
        'frames': len(scene['frames']), 'branches': len(actual), 'model_signature_verified': True}
    report = {'project': project, 'run_id': run_id, 'job_id': completed['id'], 'statuses': workflow['statuses'],
              'request_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
              'network_scene': scene_summary,
              'assessment': assessment,
              'warning_approvals': warning_approvals,
              'resource_decisions': resource_decisions,
              'applied': applied, 'trace_window_count': trace['count'], 'http': evidence,
              'browser_url': args.base_url + '/studio/results?project=' + project,
              'trace_url': args.base_url + '/trace-analysis?view=messages&project=' + project + '&job=' + completed['id']}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
