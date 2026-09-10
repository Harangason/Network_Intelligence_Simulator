"""Real HTTP acceptance through the UI proxy, in an isolated test project.

Explicit review/apply requests are confined to the newly created test project.
No LLM stub, simulation stub, or direct database writes are used.
"""
from __future__ import annotations
import argparse
from http.cookiejar import CookieJar
import json
import hashlib
import re
from pathlib import Path
import time
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:13500')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--prompt-file', type=Path, help='Replay a real wizard specification in an isolated project.')
    parser.add_argument('--initial-can-fd-segments', type=int)
    parser.add_argument('--technology', choices=['can_fd', 'ethernet'], default='can_fd')
    parser.add_argument('--complete-scope', action='store_true', help='Confirm consumers for both ECU status messages, so ALL is executable.')
    args = parser.parse_args()
    project = 'astra-e2e-' + uuid4().hex[:12]
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
    if args.initial_can_fd_segments is not None:
        assert args.initial_can_fd_segments >= 0
        prompt = prompt.replace('- Hardware-Sollwerte:',
            '- Kommunikationssystem-Sollwerte: ' + json.dumps([{'id': 'can_fd', 'count': args.initial_can_fd_segments}])
            + '\n- Hardware-Sollwerte:')
    resource_decisions = []
    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding='utf-8')
        prompt = re.sub(r'^- Lauf-ID:.*$', '- Lauf-ID: ' + run_id, prompt, flags=re.M)
    for attempt in range(8):
        message = prompt + ('\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.' if attempt else '')
        events = request('/api/engineering/agent/chat', {'prompt': message}, stream=True)
        proposals = [event['proposal'] for event in events if event.get('type') == 'APPROVAL' and event.get('proposal')]
        if not proposals:
            workflow = request('/api/engineering/workflow?view=summary')
            if all(value in {'COMPLETE', 'APPROVED', 'WARNING'} for value in workflow['statuses'].values()):
                break
            raise AssertionError({'statuses': workflow['statuses'], 'events': events[-5:]})
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
    repeated = request('/api/engineering/agent/chat', {'prompt': prompt + '\nFortsetzung des bestätigten Wizard-Auftrags: Ziel: data_science_intelligence.'}, stream=True)
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
              'network_scene': scene_summary,
              'assessment': assessment,
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
