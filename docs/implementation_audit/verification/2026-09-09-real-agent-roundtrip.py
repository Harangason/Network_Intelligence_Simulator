"""Real local-model HTTP acceptance on an isolated staging project only."""
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import httpx

base = os.environ.get('NIS_AGENT_ROUNDTRIP_BASE', 'http://127.0.0.1:15059/api/engineering')
project = 'nis-correction-agent-roundtrip-' + uuid4().hex[:10]
out = Path(os.environ.get('NIS_AGENT_ROUNDTRIP_REPORT', str(Path(__file__).with_suffix('.json'))))
report = {'project_id': project, 'base': base, 'checks': [], 'runs': []}


def save():
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


with httpx.Client(headers={'X-Project-ID': project}, timeout=700) as client:
    def request(method, path, **kwargs):
        response = client.request(method, base + path, **kwargs)
        response.raise_for_status()
        return response.json()

    node = request('POST', '/hardware-nodes', json={'name': 'AgentSmokeController', 'device_type': 'ECU', 'description': 'Vor der Freigabe'})
    node_id = str(node['id'])
    node_name = str(node['name'])
    report['hardware_id'] = node_id

    def chat(kind, prompt):
        started = time.monotonic()
        run = {'kind': kind, 'prompt': prompt, 'events': []}
        report['runs'].append(run)
        with client.stream('POST', base + '/agent/chat', json={'prompt': prompt,
            'context': {'active_project_id': project, 'selected_object_refs': [{'object_type': 'HardwareNode', 'id': node_id}]}}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if event['type'] == 'HEARTBEAT':
                    print(f'{kind}: {time.monotonic()-started:.1f}s waiting', flush=True)
                    continue
                event['elapsed_seconds'] = round(time.monotonic() - started, 3)
                run['events'].append(event)
                save()
                print(json.dumps({'kind': kind, 'elapsed': event['elapsed_seconds'], 'type': event['type'], 'status': event.get('status'), 'text': event.get('text')}, ensure_ascii=True), flush=True)
        run['elapsed_seconds'] = round(time.monotonic() - started, 3)
        save()
        return run

    read = chat('bounded-read', 'Prüfe das aktuelle Engineering-Modell und erkläre anhand des tatsächlichen Projektstands, welche Hardware-Knoten bereits vorhanden sind.')
    read_result = next(event for event in reversed(read['events']) if event['type'] == 'RESULT')
    assert read_result.get('status') == 'ANSWERED', read
    assert node_name in read_result.get('text', ''), read
    report['checks'].append('Bounded inventory answered from actual model')
    mutation = chat('mutation', f'Ändere beim Hardware-Knoten {node_name} ausschließlich die Beschreibung auf "Durch den Agenten geprüft". Erzeuge dafür einen überprüfbaren Änderungsvorschlag.')
    assert mutation['events'][-1].get('status') == 'READY_FOR_REVIEW', mutation
    proposals = [event['proposal'] for event in mutation['events'] if event.get('proposal')]
    assert len(proposals) == 1, proposals
    proposal = proposals[0]
    assert proposal['status'] == 'VALIDATED' and len(proposal['changes']) == 1, proposal
    change = proposal['changes'][0]
    assert change['object_id'] == node_id and change['action'] == 'UPDATE' and change['data'] == {'description': 'Durch den Agenten geprüft'}, change
    assert request('GET', '/hardware-nodes/' + node_id)['description'] == 'Vor der Freigabe'
    report['checks'].append('Real reasoner created exactly requested validated proposal; model unchanged before approval')
    request('PUT', '/agent/history', json={'messages': [{'id': 'http-smoke-assistant', 'role': 'assistant', 'parts': [
        {'type': 'data-engineering', 'data': {key: value for key, value in event.items() if key != 'elapsed_seconds'}}
        for event in mutation['events'] if event['type'] not in {'CONTEXT', 'HEARTBEAT'}]}]})
    save()
    path = '/agent/proposals/' + proposal['proposal_id']
    assert client.post(base + path + '/apply', json={}).status_code == 403
    csrf = request('GET', '/agent/review-session')['csrf_token']
    human = {'X-Review-CSRF': csrf, 'X-Human-Review': 'confirmed'}
    assert client.post(base + path + '/review', headers=human, json={'revision': 'stale', 'decision': 'approve'}).status_code == 409
    approved = request('POST', path + '/review', headers=human, json={'revision': proposal['revision'], 'decision': 'approve'})
    assert approved['data']['status'] == 'APPROVED', approved
    applied = request('POST', path + '/apply', headers=human, json={})
    assert applied['data']['status'] == 'APPLIED', applied
    assert request('GET', '/hardware-nodes/' + node_id)['description'] == 'Durch den Agenten geprüft'
    reloaded = request('GET', path)['data']
    assert reloaded['status'] == 'APPLIED' and len(reloaded['changes']) == 1 and len(reloaded['canonical_ids']) == 1
    history = request('GET', '/agent/history')
    references = [part['data']['proposal'] for message in history['messages'] for part in message.get('parts', []) if (part.get('data') or {}).get('proposal')]
    assert any(item['proposal_id'] == proposal['proposal_id'] and item.get('content_state') == 'REFERENCE' for item in references), history
    repeat = request('POST', path + '/apply', headers=human, json={})
    assert repeat['data']['canonical_ids'] == reloaded['canonical_ids']
    report['checks'].extend(['Missing human intent blocked (403)', 'Stale revision blocked (409)',
        'Approved proposal applied and persisted; history reload references complete proposal', 'Repeated apply idempotent'])
    report['proposal_id'] = proposal['proposal_id']
    save()
    print(json.dumps({'project_id': project, 'checks': report['checks'], 'timings': {run['kind']: run['elapsed_seconds'] for run in report['runs']}}, ensure_ascii=True), flush=True)
